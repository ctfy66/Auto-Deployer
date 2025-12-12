"""LLM Agent that autonomously controls deployment."""

from __future__ import annotations

import json
import logging
import platform
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Union, TYPE_CHECKING

import requests

from ..config import LLMConfig
from ..interaction import (
    UserInteractionHandler,
    InteractionRequest,
    InteractionResponse,
    CLIInteractionHandler,
    InputType,
    QuestionCategory,
)
from .output_extractor import CommandOutputExtractor

if TYPE_CHECKING:
    from ..ssh import RemoteHostFacts
    from ..workflow import DeploymentRequest, LocalDeploymentRequest
    from ..ssh import SSHSession
    from ..local import LocalSession, LocalHostFacts
    from ..analyzer import RepoContext
    from ..knowledge import ExperienceRetriever

logger = logging.getLogger(__name__)


def _get_repo_name(repo_url: str) -> str:
    """从仓库 URL 提取仓库名."""
    return repo_url.rstrip("/").split("/")[-1].replace(".git", "")


def _get_default_deploy_dir(repo_url: str, deploy_dir: Optional[str] = None) -> str:
    """获取默认部署目录（优先使用指定目录，否则用 ~/<repo_name>）."""
    if deploy_dir:
        return deploy_dir
    repo_name = _get_repo_name(repo_url)
    return f"~/{repo_name}"


@dataclass
class AgentAction:
    """An action decided by the LLM agent."""
    action_type: str  # "execute", "done", "failed", "ask_user"
    command: Optional[str] = None
    reasoning: Optional[str] = None
    message: Optional[str] = None
    # 用户交互相关字段
    question: Optional[str] = None              # 要问用户的问题
    options: Optional[List[str]] = None         # 可选项
    input_type: str = "choice"                  # "choice", "text", "confirm", "secret"
    category: str = "decision"                  # "decision", "confirmation", "information", "error_recovery"
    context: Optional[str] = None               # 附加上下文
    default_option: Optional[str] = None        # 默认选项


@dataclass 
class CommandResult:
    """Result of executing a command."""
    command: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int


@dataclass
class DeploymentStep:
    """部署计划中的单个步骤"""
    id: int
    name: str                                    # 如 "Install Node.js"
    description: str                             # 详细描述
    category: str                                # "prerequisite" | "setup" | "build" | "deploy" | "verify"
    estimated_commands: List[str] = field(default_factory=list)  # 预计执行的命令（参考用）
    success_criteria: str = ""                   # 成功标准
    depends_on: List[int] = field(default_factory=list)  # 依赖的步骤ID


@dataclass
class DeploymentPlan:
    """完整的部署方案"""
    strategy: str                                # "docker-compose" | "docker" | "traditional" | "static"
    components: List[str] = field(default_factory=list)  # ["nodejs", "nginx", "pm2"]
    steps: List[DeploymentStep] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)       # 已识别的风险
    notes: List[str] = field(default_factory=list)       # 注意事项
    estimated_time: str = ""                     # 预计时间
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典用于日志记录"""
        return {
            "strategy": self.strategy,
            "components": self.components,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "estimated_commands": s.estimated_commands,
                    "success_criteria": s.success_criteria,
                    "depends_on": s.depends_on,
                }
                for s in self.steps
            ],
            "risks": self.risks,
            "notes": self.notes,
            "estimated_time": self.estimated_time,
            "created_at": self.created_at,
        }


class DeploymentAgent:
    """
    LLM-powered agent that autonomously deploys applications.
    
    The agent operates in a loop:
    1. Observe: See the current state (repo info, command history)
    2. Think: LLM decides what to do next
    3. Act: Execute the command OR ask user for input
    4. Repeat until done or max iterations reached
    """

    def __init__(
        self,
        config: LLMConfig,
        max_iterations: int = 30,
        log_dir: Optional[str] = None,
        interaction_handler: Optional[UserInteractionHandler] = None,
        experience_retriever: Optional["ExperienceRetriever"] = None,
        enable_planning: bool = True,
        require_plan_approval: bool = False,
        planning_timeout: int = 60,
    ) -> None:
        if not config.api_key:
            raise ValueError("Agent requires an API key")
        self.config = config
        self.max_iterations = max_iterations
        self.session = requests.Session()
        
        # 用户交互处理器 - 默认使用 CLI
        self.interaction_handler = interaction_handler or CLIInteractionHandler()
        
        # 经验检索器（可选）
        self.experience_retriever = experience_retriever
        
        # 规划阶段配置
        self.enable_planning = enable_planning
        self.require_plan_approval = require_plan_approval
        self.planning_timeout = planning_timeout
        
        # 当前部署计划
        self.current_plan: Optional[DeploymentPlan] = None
        self.current_plan_step: int = 0
        
        # 日志目录
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "agent_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前部署的日志文件
        self.current_log_file: Optional[Path] = None
        self.deployment_log: dict = {}
        
        # 用户交互历史（发送给 LLM）
        self.user_interactions: List[dict] = []
        
        # Initialize LLM provider
        from .base import create_llm_provider
        self.llm_provider = create_llm_provider(config)
        logger.info("Using LLM provider: %s (model: %s)", config.provider, config.model)

        # Keep session for backward compatibility (not used with new providers)
        self.session = requests.Session()
        import os
        proxy = config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        # Legacy endpoint (for backward compatibility only)
        self.base_endpoint = config.endpoint or (
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
        )

        # 执行历史
        self.history: List[dict] = []

        # 输出提取器
        self.output_extractor = CommandOutputExtractor(
            max_success_lines=30,  # 成功时最多30行
            max_error_lines=50     # 失败时最多50行
        )

    def deploy(
        self,
        request: "DeploymentRequest",
        host_facts: Optional["RemoteHostFacts"],
        ssh_session: "SSHSession",
        repo_context: Optional["RepoContext"] = None,
    ) -> bool:
        """
        Run the autonomous deployment loop.
        
        Args:
            request: Deployment request with repo URL and SSH details
            host_facts: Information about the remote host
            ssh_session: Active SSH session
            repo_context: Pre-analyzed repository context (optional but recommended)
            
        Returns True if deployment succeeded, False otherwise.
        """
        # 打印详细的配置信息
        deploy_dir = _get_default_deploy_dir(request.repo_url, request.deploy_dir)
        logger.info("=" * 60)
        logger.info("🚀 Auto-Deployer Agent Starting")
        logger.info("=" * 60)
        logger.info("📋 Configuration:")
        logger.info("   LLM Model:      %s", self.config.model)
        logger.info("   LLM Endpoint:   %s", self.base_endpoint[:50] + "..." if len(self.base_endpoint) > 50 else self.base_endpoint)
        logger.info("   Max Iterations: %d", self.max_iterations)
        logger.info("   Temperature:    %.2f", self.config.temperature)
        logger.info("")
        logger.info("🎯 Deployment Target:")
        logger.info("   Repository:     %s", request.repo_url)
        logger.info("   Server:         %s@%s:%d", request.username, request.host, request.port)
        logger.info("   Deploy Dir:     %s", deploy_dir)
        logger.info("   Auth Method:    %s", request.auth_method)
        if host_facts:
            logger.info("")
            logger.info("🖥️  Remote Host Info:")
            logger.info("   Hostname:       %s", host_facts.hostname)
            logger.info("   OS:             %s", host_facts.os_release)
            logger.info("   Kernel:         %s", host_facts.kernel)
        if repo_context:
            logger.info("")
            logger.info("📦 Repository Analysis:")
            logger.info("   Project Type:   %s", repo_context.project_type or "unknown")
            logger.info("   Framework:      %s", repo_context.detected_framework or "none detected")
            logger.info("   Scripts:        %s", ", ".join(repo_context.detected_scripts) if repo_context.detected_scripts else "none")
        logger.info("=" * 60)
        logger.info("")
        
        # 初始化日志记录
        self._init_deployment_log(request)
        
        # 初始化上下文 - 包含预分析的仓库信息
        self.history = []
        self.user_interactions = []
        self.current_plan = None
        self.current_plan_step = 0
        context = self._build_initial_context(request, host_facts, repo_context)
        
        # 记录初始上下文
        self.deployment_log["context"] = {
            "repo_url": context.get("repo_url"),
            "deploy_dir": context.get("deploy_dir"),
            "ssh_target": context.get("ssh_target"),
            "has_repo_analysis": repo_context is not None,
            "project_type": repo_context.project_type if repo_context else None,
            "framework": repo_context.detected_framework if repo_context else None,
        }
        
        # 🆕 Phase 1: 创建部署计划
        if self.enable_planning:
            logger.info("📋 Phase 1: Creating deployment plan...")
            self.current_plan = self._create_deployment_plan(context, repo_context)
            
            if self.current_plan:
                # 显示计划
                self._display_plan(self.current_plan)
                
                # 记录计划到日志
                self.deployment_log["plan"] = self.current_plan.to_dict()
                self.deployment_log["plan_execution"] = {
                    "current_step": 0,
                    "completed_steps": [],
                    "skipped_steps": [],
                    "adjusted_steps": [],
                }
                self._save_deployment_log()
                
                # 用户确认（如果需要）
                if self.require_plan_approval:
                    response = self._ask_plan_approval(self.current_plan)
                    if response.cancelled:
                        logger.info("❌ User cancelled deployment")
                        self.deployment_log["status"] = "cancelled"
                        self.deployment_log["end_time"] = datetime.now().isoformat()
                        self._save_deployment_log()
                        return False
                
                logger.info("")
                logger.info("🚀 Phase 2: Executing deployment plan...")
                logger.info("")
            else:
                logger.warning("⚠️  Failed to create deployment plan, falling back to reactive mode")
        
        for iteration in range(1, self.max_iterations + 1):
            # 显示进度（如果有计划）
            if self.current_plan and self.current_plan_step < len(self.current_plan.steps):
                step = self.current_plan.steps[self.current_plan_step]
                total = len(self.current_plan.steps)
                logger.info(f"📍 Step {self.current_plan_step + 1}/{total}: {step.name} (Iteration {iteration})")
            else:
                logger.info(f"📍 Iteration {iteration}/{self.max_iterations}")
            
            # 让 LLM 决定下一步
            action = self._think(context)
            
            # 记录 LLM 的决策
            step_log = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "action": action.action_type,
                "command": action.command,
                "reasoning": action.reasoning,
                "message": action.message,
            }
            
            if action.action_type == "done":
                step_log["result"] = "SUCCESS"
                self.deployment_log["steps"].append(step_log)
                self.deployment_log["status"] = "success"
                self.deployment_log["end_time"] = datetime.now().isoformat()
                self._save_deployment_log()
                logger.info(f"✅ Agent completed: {action.message}")
                logger.info(f"📄 Log saved to: {self.current_log_file}")
                return True
            
            if action.action_type == "failed":
                step_log["result"] = "FAILED"
                self.deployment_log["steps"].append(step_log)
                self.deployment_log["status"] = "failed"
                self.deployment_log["end_time"] = datetime.now().isoformat()
                self._save_deployment_log()
                logger.error(f"❌ Agent gave up: {action.message}")
                logger.info(f"📄 Log saved to: {self.current_log_file}")
                return False
            
            if action.action_type == "execute" and action.command:
                logger.info(f"🔧 Executing: {action.command}")
                if action.reasoning:
                    logger.info(f"   💭 Reason: {action.reasoning}")
                
                # 执行命令
                result = self._execute_command(ssh_session, action.command)

                # 使用智能提取器处理输出
                extracted = self.output_extractor.extract(
                    stdout=result.stdout or "",
                    stderr=result.stderr or "",
                    success=result.success,
                    exit_code=result.exit_code,
                    command=action.command
                )
                
                # 格式化为LLM可读的输出
                formatted_output = self.output_extractor.format_for_llm(extracted)
                
                # 打印到终端 - 显示提取后的输出
                print("\n" + "=" * 60)
                print("📤 LLM将看到的提取后输出:")
                print("-" * 60)
                print(formatted_output)
                print("=" * 60 + "\n")

                # 记录命令结果（完整保存到日志文件）
                step_log["result"] = {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "extracted_output": formatted_output,  # 提取后的输出
                    "stdout": result.stdout[:2000] if result.stdout else "",  # 原始输出
                    "stderr": result.stderr[:2000] if result.stderr else "",  # 原始错误
                    "extracted_summary": extracted.summary,
                }
                self.deployment_log["steps"].append(step_log)

                # 记录到历史（使用提取后的输出，节省上下文）
                self.history.append({
                    "iteration": iteration,
                    "reasoning": action.reasoning,
                    "command": action.command,
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "output_summary": extracted.summary,
                    "key_info": extracted.key_info[:5],  # 最多5条关键信息
                    "error_context": extracted.error_context[:500] if extracted.error_context else None,
                })
                
                # 显示结果
                status = "✓" if result.success else "✗"
                logger.info(f"   {status} Exit code: {result.exit_code}")
                if result.stdout:
                    logger.debug(f"   stdout: {result.stdout[:200]}")
                if result.stderr and not result.success:
                    logger.warning(f"   stderr: {result.stderr[:200]}")
                
                # 每步都保存日志（防止中断丢失）
                self._save_deployment_log()
            
            elif action.action_type == "ask_user" and action.question:
                # 处理用户交互请求
                logger.info(f"💬 Agent asking user: {action.question[:50]}...")
                if action.reasoning:
                    logger.info(f"   Reason: {action.reasoning}")
                
                # 创建交互请求
                user_response = self._ask_user(action)
                
                # 记录到日志
                step_log["question"] = action.question
                step_log["options"] = action.options
                step_log["result"] = {
                    "user_response": user_response.value,
                    "cancelled": user_response.cancelled,
                    "is_custom": user_response.is_custom,
                }
                self.deployment_log["steps"].append(step_log)
                
                # 如果用户取消，终止部署
                if user_response.cancelled:
                    logger.info("   用户取消了操作")
                    self.deployment_log["status"] = "cancelled"
                    self.deployment_log["end_time"] = datetime.now().isoformat()
                    self._save_deployment_log()
                    logger.info(f"📄 Log saved to: {self.current_log_file}")
                    return False
                
                # 记录用户回复到交互历史
                self.user_interactions.append({
                    "iteration": iteration,
                    "question": action.question,
                    "options": action.options,
                    "user_response": user_response.value,
                    "is_custom": user_response.is_custom,
                })
                
                logger.info(f"   用户回复: {user_response.value}")
                self._save_deployment_log()
            
            else:
                logger.warning(f"Unknown action: {action.action_type}")
        
        self.deployment_log["status"] = "max_iterations"
        self.deployment_log["end_time"] = datetime.now().isoformat()
        self._save_deployment_log()
        logger.error("❌ Agent reached max iterations without completing")
        logger.info(f"📄 Log saved to: {self.current_log_file}")
        return False

    def deploy_local(
        self,
        request: "LocalDeploymentRequest",
        host_facts: Optional["LocalHostFacts"],
        local_session: "LocalSession",
        repo_context: Optional["RepoContext"] = None,
    ) -> bool:
        """
        Run the autonomous deployment loop locally.
        
        Args:
            request: Local deployment request with repo URL
            host_facts: Information about the local host
            local_session: Local command execution session
            repo_context: Pre-analyzed repository context (optional but recommended)
            
        Returns True if deployment succeeded, False otherwise.
        """
        # 打印详细的配置信息
        logger.info("=" * 60)
        logger.info("🚀 Auto-Deployer Agent Starting (LOCAL MODE)")
        logger.info("=" * 60)
        logger.info("📋 Configuration:")
        logger.info("   LLM Model:      %s", self.config.model)
        logger.info("   LLM Endpoint:   %s", self.base_endpoint[:50] + "..." if len(self.base_endpoint) > 50 else self.base_endpoint)
        logger.info("   Max Iterations: %d", self.max_iterations)
        logger.info("   Temperature:    %.2f", self.config.temperature)
        logger.info("")
        logger.info("🎯 Deployment Target:")
        logger.info("   Repository:     %s", request.repo_url)
        logger.info("   Mode:           LOCAL (this machine)")
        deploy_dir = _get_default_deploy_dir(request.repo_url, request.deploy_dir)
        logger.info("   Deploy Dir:     %s", deploy_dir)
        if host_facts:
            logger.info("")
            logger.info("🖥️  Local Host Info:")
            logger.info("   Hostname:       %s", host_facts.hostname)
            logger.info("   OS:             %s", host_facts.os_release)
            logger.info("   Architecture:   %s", host_facts.architecture)
        if repo_context:
            logger.info("")
            logger.info("📦 Repository Analysis:")
            logger.info("   Project Type:   %s", repo_context.project_type or "unknown")
            logger.info("   Framework:      %s", repo_context.detected_framework or "none detected")
            logger.info("   Scripts:        %s", ", ".join(repo_context.detected_scripts) if repo_context.detected_scripts else "none")
        logger.info("=" * 60)
        logger.info("")
        
        # 初始化日志记录
        self._init_local_deployment_log(request, host_facts)
        
        # 初始化上下文
        self.history = []
        self.user_interactions = []
        self.current_plan = None
        self.current_plan_step = 0
        context = self._build_local_initial_context(request, host_facts, repo_context)
        
        # 记录初始上下文
        self.deployment_log["context"] = {
            "repo_url": context.get("repo_url"),
            "deploy_dir": deploy_dir,
            "os": host_facts.os_name if host_facts else platform.system(),
            "has_repo_analysis": repo_context is not None,
            "project_type": repo_context.project_type if repo_context else None,
            "framework": repo_context.detected_framework if repo_context else None,
        }
        
        # 🆕 Phase 1: 创建部署计划
        if self.enable_planning:
            logger.info("📋 Phase 1: Creating deployment plan...")
            self.current_plan = self._create_deployment_plan(context, repo_context)
            
            if self.current_plan:
                # 显示计划
                self._display_plan(self.current_plan)
                
                # 记录计划到日志
                self.deployment_log["plan"] = self.current_plan.to_dict()
                self.deployment_log["plan_execution"] = {
                    "current_step": 0,
                    "completed_steps": [],
                    "skipped_steps": [],
                    "adjusted_steps": [],
                }
                self._save_deployment_log()
                
                # 用户确认（如果需要）
                if self.require_plan_approval:
                    response = self._ask_plan_approval(self.current_plan)
                    if response.cancelled:
                        logger.info("❌ User cancelled deployment")
                        self.deployment_log["status"] = "cancelled"
                        self.deployment_log["end_time"] = datetime.now().isoformat()
                        self._save_deployment_log()
                        return False
                
                logger.info("")
                logger.info("🚀 Phase 2: Executing deployment plan...")
                logger.info("")
            else:
                logger.warning("⚠️  Failed to create deployment plan, falling back to reactive mode")
        
        for iteration in range(1, self.max_iterations + 1):
            # 显示进度（如果有计划）
            if self.current_plan and self.current_plan_step < len(self.current_plan.steps):
                step = self.current_plan.steps[self.current_plan_step]
                total = len(self.current_plan.steps)
                logger.info(f"📍 Step {self.current_plan_step + 1}/{total}: {step.name} (Iteration {iteration})")
            else:
                logger.info(f"📍 Iteration {iteration}/{self.max_iterations}")
            
            # 让 LLM 决定下一步
            action = self._think_local(context)
            
            # 记录 LLM 的决策
            step_log = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "action": action.action_type,
                "command": action.command,
                "reasoning": action.reasoning,
                "message": action.message,
            }
            
            if action.action_type == "done":
                step_log["result"] = "SUCCESS"
                self.deployment_log["steps"].append(step_log)
                self.deployment_log["status"] = "success"
                self.deployment_log["end_time"] = datetime.now().isoformat()
                self._save_deployment_log()
                logger.info(f"✅ Agent completed: {action.message}")
                logger.info(f"📄 Log saved to: {self.current_log_file}")
                return True
            
            if action.action_type == "failed":
                step_log["result"] = "FAILED"
                self.deployment_log["steps"].append(step_log)
                self.deployment_log["status"] = "failed"
                self.deployment_log["end_time"] = datetime.now().isoformat()
                self._save_deployment_log()
                logger.error(f"❌ Agent gave up: {action.message}")
                logger.info(f"📄 Log saved to: {self.current_log_file}")
                return False
            
            if action.action_type == "execute" and action.command:
                logger.info(f"🔧 Executing: {action.command}")
                if action.reasoning:
                    logger.info(f"   💭 Reason: {action.reasoning}")
                
                # 执行本地命令
                result = self._execute_local_command(local_session, action.command)
                
                # 使用智能提取器处理输出
                extracted = self.output_extractor.extract(
                    stdout=result.stdout or "",
                    stderr=result.stderr or "",
                    success=result.success,
                    exit_code=result.exit_code,
                    command=action.command
                )
                
                # 格式化为LLM可读的输出
                formatted_output = self.output_extractor.format_for_llm(extracted)
                
                # 打印到终端 - 显示提取后的输出
                print("\n" + "=" * 60)
                print("📤 LLM将看到的提取后输出:")
                print("-" * 60)
                print(formatted_output)
                print("=" * 60 + "\n")
                
                # 记录命令结果
                step_log["result"] = {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "extracted_output": formatted_output,  # 提取后的输出
                    "stdout": result.stdout[:2000] if result.stdout else "",  # 原始输出
                    "stderr": result.stderr[:2000] if result.stderr else "",  # 原始错误
                    "extracted_summary": extracted.summary,
                }
                self.deployment_log["steps"].append(step_log)
                
                # 记录到历史
                self.history.append({
                    "iteration": iteration,
                    "reasoning": action.reasoning,
                    "command": action.command,
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout[:1000] if result.stdout else "",
                    "stderr": result.stderr[:1000] if result.stderr else "",
                })
                
                # 显示结果
                status = "✓" if result.success else "✗"
                logger.info(f"   {status} Exit code: {result.exit_code}")
                if result.stdout:
                    logger.debug(f"   stdout: {result.stdout[:200]}")
                if result.stderr and not result.success:
                    logger.warning(f"   stderr: {result.stderr[:200]}")
                
                self._save_deployment_log()
            
            elif action.action_type == "ask_user" and action.question:
                # 处理用户交互请求
                logger.info(f"💬 Agent asking user: {action.question[:50]}...")
                if action.reasoning:
                    logger.info(f"   Reason: {action.reasoning}")
                
                user_response = self._ask_user(action)
                
                step_log["question"] = action.question
                step_log["options"] = action.options
                step_log["result"] = {
                    "user_response": user_response.value,
                    "cancelled": user_response.cancelled,
                    "is_custom": user_response.is_custom,
                }
                self.deployment_log["steps"].append(step_log)
                
                if user_response.cancelled:
                    logger.info("   用户取消了操作")
                    self.deployment_log["status"] = "cancelled"
                    self.deployment_log["end_time"] = datetime.now().isoformat()
                    self._save_deployment_log()
                    return False
                
                self.user_interactions.append({
                    "iteration": iteration,
                    "question": action.question,
                    "options": action.options,
                    "user_response": user_response.value,
                    "is_custom": user_response.is_custom,
                })
                
                logger.info(f"   用户回复: {user_response.value}")
                self._save_deployment_log()
            
            else:
                logger.warning(f"Unknown action: {action.action_type}")
        
        self.deployment_log["status"] = "max_iterations"
        self.deployment_log["end_time"] = datetime.now().isoformat()
        self._save_deployment_log()
        logger.error("❌ Agent reached max iterations without completing")
        logger.info(f"📄 Log saved to: {self.current_log_file}")
        return False

    def _init_local_deployment_log(self, request: "LocalDeploymentRequest", host_facts: Optional["LocalHostFacts"] = None) -> None:
        """Initialize a new deployment log file for local deployment."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_name = _get_repo_name(request.repo_url)
        filename = f"deploy_local_{repo_name}_{timestamp}.json"
        self.current_log_file = self.log_dir / filename
        
        deploy_dir = _get_default_deploy_dir(request.repo_url, request.deploy_dir)
        self.deployment_log = {
            "mode": "local",
            "repo_url": request.repo_url,
            "target": f"local:{platform.node()}",
            "deploy_dir": deploy_dir,
            "os": host_facts.os_name if host_facts else platform.system(),
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "config": {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_iterations": self.max_iterations,
                "endpoint": self.base_endpoint,
            },
            "context": {},
            "steps": [],
        }
        logger.info(f"📝 Logging to: {self.current_log_file}")

    def _init_deployment_log(self, request: "DeploymentRequest") -> None:
        """Initialize a new deployment log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 从 repo_url 提取项目名
        repo_name = _get_repo_name(request.repo_url)
        filename = f"deploy_{repo_name}_{timestamp}.json"
        self.current_log_file = self.log_dir / filename
        
        deploy_dir = _get_default_deploy_dir(request.repo_url, request.deploy_dir)
        self.deployment_log = {
            "repo_url": request.repo_url,
            "target": f"{request.username}@{request.host}:{request.port}",
            "deploy_dir": deploy_dir,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "config": {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_iterations": self.max_iterations,
                "endpoint": self.base_endpoint,
            },
            "context": {},
            "steps": [],
        }
        logger.info(f"📝 Logging to: {self.current_log_file}")

    def _save_deployment_log(self) -> None:
        """Save the deployment log to file."""
        if self.current_log_file:
            with open(self.current_log_file, "w", encoding="utf-8") as f:
                json.dump(self.deployment_log, f, indent=2, ensure_ascii=False)

    def _build_local_initial_context(
        self,
        request: "LocalDeploymentRequest",
        host_facts: Optional["LocalHostFacts"],
        repo_context: Optional["RepoContext"] = None,
    ) -> dict:
        """Build the initial context for local deployment."""
        deploy_dir = _get_default_deploy_dir(request.repo_url, request.deploy_dir)
        ctx = {
            "repo_url": request.repo_url,
            "deploy_dir": deploy_dir,
            "mode": "local",
            "local_host": host_facts.to_payload() if host_facts else {
                "os_name": platform.system(),
                "os_release": platform.platform(),
            },
        }
        
        # 添加预分析的仓库信息
        if repo_context:
            ctx["repo_analysis"] = repo_context.to_prompt_context()
            ctx["project_type"] = repo_context.project_type
            ctx["framework"] = repo_context.detected_framework
            ctx["scripts"] = repo_context.detected_scripts
        
        return ctx

    def _execute_local_command(self, session: "LocalSession", command: str) -> CommandResult:
        """Execute a command locally."""
        try:
            result = session.run(command, timeout=600, idle_timeout=120)  # 本地命令给更长超时
            return CommandResult(
                command=command,
                success=result.ok,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_status,
            )
        except Exception as exc:
            return CommandResult(
                command=command,
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
            )

    def _think_local(self, context: dict) -> AgentAction:
        """Ask LLM to decide the next action for local deployment."""
        prompt = self._build_local_prompt(context)

        # Use provider to generate response
        text = self.llm_provider.generate_response(
            prompt=prompt,
            response_format="json",
            timeout=60,
            max_retries=3
        )

        if not text:
            logger.error("No response from LLM")
            return AgentAction(action_type="failed", message="No LLM response")

        return self._parse_action(text)

    def _build_local_prompt(self, context: dict) -> str:
        """Build the prompt for local deployment."""
        
        os_name = context.get("local_host", {}).get("os_name", platform.system())
        is_windows = os_name == "Windows"
        
        has_repo_analysis = "repo_analysis" in context
        
        # 用户交互说明
        user_interaction_guide = """
# 🗣️ User Interaction
You can ask the user for input when needed:
```json
{
  "action": "ask_user",
  "question": "Which port should the app run on?",
  "options": ["3000", "8080", "5000"],
  "input_type": "choice",
  "category": "decision",
  "reasoning": "Multiple ports available"
}
```
"""

        if is_windows:
            system_prompt = f"""# Role
You are an autonomous DevOps deployment agent. You execute **PowerShell commands** on a **Windows** machine to deploy applications.

# Goal  
Deploy the given repository locally and ensure the application is running.

# Environment
- Operating System: Windows ({os_name})
- Shell: PowerShell
- Commands you output will be executed via PowerShell
- Working directory is user's home folder
- Deploy to: {context.get('deploy_dir')}

# Available Actions
Respond with JSON:
```json
{{"action": "execute", "command": "PowerShell command", "reasoning": "why"}}
{{"action": "done", "message": "success message"}}
{{"action": "failed", "message": "error message"}}
{{"action": "ask_user", "question": "...", "options": [...], "input_type": "choice"}}
```

# ⚠️ Windows PowerShell Commands
Use PowerShell syntax:
- Clone: `git clone <repo> $env:USERPROFILE\\app`
- Remove folder: `Remove-Item -Recurse -Force $env:USERPROFILE\\app`
- Install npm: `npm install`
- Run background: `Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "start" -RedirectStandardOutput "app.log"`
- Check process: `Get-Process -Name node -ErrorAction SilentlyContinue`
- Read file: `Get-Content package.json`
- Check port: `netstat -ano | findstr :3000`
- Kill process: `Stop-Process -Id <PID> -Force`
- Environment: `$env:VARNAME = "value"`

# CRITICAL RULES
1. Use PowerShell syntax, NOT bash/Linux commands!
2. Use `$env:USERPROFILE` instead of `~` for home directory
3. For long-running servers, use `Start-Process` with `-NoNewWindow`
4. Path separators: use `\\` or `/` (PowerShell accepts both)
""" + user_interaction_guide
        else:
            system_prompt = f"""# Role
You are an autonomous DevOps deployment agent. You execute shell commands on a **{os_name}** machine to deploy applications.

# Goal  
Deploy the given repository locally and ensure the application is running.

# Environment
- Operating System: {os_name}
- Shell: bash
- Commands you output will be executed directly
- Working directory is user's home folder
- Deploy to: {context.get('deploy_dir')}

# Available Actions
Respond with JSON:
```json
{{"action": "execute", "command": "shell command", "reasoning": "why"}}
{{"action": "done", "message": "success message"}}
{{"action": "failed", "message": "error message"}}
{{"action": "ask_user", "question": "...", "options": [...], "input_type": "choice"}}
```

# CRITICAL RULES
1. For servers, use nohup: `nohup npm start > app.log 2>&1 &`
2. Wait after starting: `sleep 3`
3. Verify with curl and check HTTP status code:
   - `curl -s -o /dev/null -w "%{http_code}" http://localhost:<port>`
   - Only HTTP 200 = success! 301/302/404/5xx = FAILED, need to fix!
""" + user_interaction_guide

        # 构建当前状态
        state = {
            "repo_url": context.get("repo_url"),
            "deploy_dir": context.get("deploy_dir"),
            "os": os_name,
            "command_history": self.history[-10:],
        }
        
        if self.user_interactions:
            state["user_interactions"] = self.user_interactions[-5:]
        
        parts = [system_prompt, "\n---\n"]
        
        # 添加部署计划上下文（如果有）
        plan_context = self._get_plan_context_for_prompt()
        if plan_context:
            parts.append(plan_context)
            parts.append("\n---\n")
        
        if has_repo_analysis:
            parts.append("# Pre-Analyzed Repository Context")
            parts.append(context["repo_analysis"])
            parts.append("\n---\n")
        
        parts.append("# Current State")
        parts.append(f"```json\n{json.dumps(state, indent=2, ensure_ascii=False)}\n```")
        
        if self.user_interactions:
            last_interaction = self.user_interactions[-1]
            parts.append(f"\n⚠️ User responded: \"{last_interaction['user_response']}\"")
        
        parts.append("\nDecide your next action. Respond with JSON only.")
        
        return "\n".join(parts)

    def _ask_user(self, action: AgentAction) -> InteractionResponse:
        """Ask user for input based on agent's request."""
        # 映射 input_type
        input_type_map = {
            "choice": InputType.CHOICE,
            "text": InputType.TEXT,
            "confirm": InputType.CONFIRM,
            "secret": InputType.SECRET,
        }
        input_type = input_type_map.get(action.input_type, InputType.CHOICE)
        
        # 映射 category
        category_map = {
            "decision": QuestionCategory.DECISION,
            "confirmation": QuestionCategory.CONFIRMATION,
            "information": QuestionCategory.INFORMATION,
            "error_recovery": QuestionCategory.ERROR_RECOVERY,
            "custom": QuestionCategory.CUSTOM,
        }
        category = category_map.get(action.category, QuestionCategory.DECISION)
        
        # 创建交互请求
        request = InteractionRequest(
            question=action.question or "",
            input_type=input_type,
            options=action.options or [],
            category=category,
            context=action.context,
            default=action.default_option,
            allow_custom=True,
        )
        
        # 使用交互处理器获取用户响应
        return self.interaction_handler.ask(request)

    def _think(self, context: dict) -> AgentAction:
        """Ask LLM to decide the next action."""
        prompt = self._build_prompt(context)

        # Use provider to generate response
        text = self.llm_provider.generate_response(
            prompt=prompt,
            response_format="json",
            timeout=60,
            max_retries=3
        )

        if not text:
            logger.error("No response from LLM")
            return AgentAction(action_type="failed", message="No LLM response")

        return self._parse_action(text)

    def _parse_action(self, text: str) -> AgentAction:
        """Parse LLM response into an action."""
        try:
            data = json.loads(text)
            return AgentAction(
                action_type=data.get("action", "failed"),
                command=data.get("command"),
                reasoning=data.get("reasoning"),
                message=data.get("message"),
                # 用户交互相关字段
                question=data.get("question"),
                options=data.get("options"),
                input_type=data.get("input_type", "choice"),
                category=data.get("category", "decision"),
                context=data.get("context"),
                default_option=data.get("default"),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            return AgentAction(action_type="failed", message=f"Parse error: {text[:100]}")

    def _execute_command(self, session: "SSHSession", command: str) -> CommandResult:
        """Execute a command on the remote server."""
        try:
            result = session.run(command, timeout=600, idle_timeout=60)
            return CommandResult(
                command=command,
                success=result.ok,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.exit_status,
            )
        except Exception as exc:
            return CommandResult(
                command=command,
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=-1,
            )

    def _build_initial_context(
        self,
        request: "DeploymentRequest",
        host_facts: Optional["RemoteHostFacts"],
        repo_context: Optional["RepoContext"] = None,
    ) -> dict:
        """Build the initial context for the agent."""
        deploy_dir = _get_default_deploy_dir(request.repo_url, request.deploy_dir)
        ctx = {
            "repo_url": request.repo_url,
            "deploy_dir": deploy_dir,
            "ssh_target": f"{request.username}@{request.host}:{request.port}",
            "remote_host": host_facts.to_payload() if host_facts else None,
        }
        
        # 添加预分析的仓库信息
        if repo_context:
            ctx["repo_analysis"] = repo_context.to_prompt_context()
            ctx["project_type"] = repo_context.project_type
            ctx["framework"] = repo_context.detected_framework
            ctx["scripts"] = repo_context.detected_scripts
        
        return ctx
    
    def _detect_target_os(self, context: dict) -> str:
        """检测目标操作系统"""
        # 优先从remote_host或local_host获取
        if "remote_host" in context and context["remote_host"]:
            os_name = context["remote_host"].get("os_name", "").lower()
            if "windows" in os_name or os_name == "windows":
                return "windows"
            elif "linux" in os_name or os_name == "linux":
                return "linux"
            elif "darwin" in os_name:
                return "macos"
        
        if "local_host" in context and context["local_host"]:
            os_name = context["local_host"].get("os_name", "").lower()
            if "windows" in os_name or os_name == "windows":
                return "windows"
            elif "linux" in os_name or os_name == "linux":
                return "linux"
            elif "darwin" in os_name:
                return "macos"
        
        # 默认：本地模式用Windows（面向小白用户），SSH模式用Linux
        if context.get("mode") == "local":
            return "windows"  # 小白用户大多用Windows
        else:
            return "linux"  # SSH通常是Linux服务器
    
    def _build_os_specific_prompt(self, target_os: str) -> str:
        """根据目标OS构建特定的系统提示词"""
        
        if target_os == "windows":
            return self._build_windows_prompt()
        elif target_os == "macos":
            return self._build_macos_prompt()
        else:  # linux
            return self._build_linux_prompt()
    
    def _build_windows_prompt(self) -> str:
        """Windows系统的提示词"""
        return """# Role
You are an intelligent deployment agent for **Windows systems**. You can execute PowerShell commands to deploy applications locally.

# Goal  
Deploy the given repository on this Windows machine and ensure the application is running.
**Success criteria**: Application responds to HTTP requests with actual content (for web apps).

# Your Capabilities
- Execute PowerShell commands on Windows
- Can run ANY command on this Windows machine
- Can install software (using winget, chocolatey, or installers)
- Can ask the user for input when needed

# 🧠 THINK LIKE A WINDOWS DEVOPS EXPERT

You are deploying on **Windows**, NOT Linux! Use Windows-appropriate commands.

## Windows Command Reference

### File Operations
```powershell
# List files
Get-ChildItem
dir

# Change directory
cd C:\\path\\to\\dir

# Create directory
New-Item -ItemType Directory -Force -Path "mydir"
mkdir mydir  # also works

# Remove directory
Remove-Item -Recurse -Force "mydir"

# Copy files
Copy-Item -Path "source" -Destination "dest" -Recurse

# Check if file exists
Test-Path "file.txt"
```

### Process Management
```powershell
# Start background process
Start-Process -NoNewWindow -FilePath "node" -ArgumentList "server.js"

# Or use npm (it handles Windows properly)
npm start

# Check running processes
Get-Process -Name "node"

# Kill process
Stop-Process -Name "node" -Force
```

### Environment Variables
```powershell
# Set environment variable
$env:NODE_ENV = "production"
$env:PORT = "3000"

# View environment variable
$env:PATH
```

### Package Installation
```powershell
# Node.js packages
npm install
npm install -g pm2

# Python packages
pip install -r requirements.txt

# System packages (if chocolatey available)
choco install nodejs -y
choco install git -y

# Or use winget
winget install --id=Git.Git -e
```

### Path Handling
```powershell
# Home directory
$env:USERPROFILE   # C:\\Users\\YourName

# Current directory
(Get-Location).Path

# Join paths (use this instead of /)
Join-Path $env:USERPROFILE "myproject"
```

## Deployment Strategies for Windows

### Strategy 1: Docker Desktop (Recommended)
If Docker Desktop is installed on Windows:
```powershell
cd $project_dir
docker-compose up -d --build
# or
docker build -t myapp .
docker run -d -p 3000:3000 myapp
```

### Strategy 2: Node.js Application (MANDATORY: Use Local Dependencies)
```powershell
cd $project_dir

# STEP 1: Install dependencies locally (NEVER use -g)
npm install

# STEP 2: Build if needed
npm run build

# STEP 3: Start application
# Option A: Use npm scripts (recommended)
npm start

# Option B: Use local PM2 via npx (better for production)
npm install pm2  # Install locally, NOT globally
npx pm2 start server.js --name myapp
npx pm2 save
npx pm2 list  # Verify it's running

# Option C: Direct node execution
node server.js
```

**Why local dependencies are mandatory:**
- ❌ `npm install -g pm2` → Global install → version conflicts across projects
- ✅ `npm install pm2` + `npx pm2` → Local install → isolated per project

### Strategy 3: Python Application (MANDATORY: Use Virtual Environment)
```powershell
cd $project_dir

# STEP 1: Create virtual environment (MANDATORY)
python -m venv venv

# STEP 2: Activate virtual environment (MANDATORY)
.\venv\Scripts\Activate.ps1
# If execution policy error, run:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# STEP 3: Verify activation (should see venv path)
Get-Command python | Select-Object Source

# STEP 4: Install dependencies in isolated environment
pip install -r requirements.txt

# STEP 5: Run application with venv Python
python app.py
# or for FastAPI/ASGI apps:
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# For background process:
Start-Process -NoNewWindow -FilePath ".\venv\Scripts\python.exe" -ArgumentList "app.py"
```

**Why virtual environment is mandatory:**
- ❌ Without venv: Dependencies install to system Python → version conflicts
- ✅ With venv: Dependencies isolated → safe and reproducible

### Strategy 4: Static Website
```powershell
# Build if needed
npm run build

# Serve with Python
cd dist
python -m http.server 8080

# Or use Node.js serve
npm install -g serve
serve -s dist -l 3000
```

## ⚠️ Critical Windows Differences

1. **Paths use backslashes**: `C:\\Users\\Name\\project` (but forward slashes often work too)
2. **No sudo**: You already have permissions or need to ask user to run as Administrator
3. **PowerShell syntax**: Different from bash (`$env:VAR` not `export VAR`)
4. **Case insensitive**: Filenames are case-insensitive
5. **Line endings**: CRLF not LF (usually handled automatically)

## Verification Strategy

**For web applications:**
```powershell
# Check HTTP status
Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing
# Check the StatusCode property

# Or use curl (if available)
curl http://localhost:3000
```

**For processes:**
```powershell
Get-Process -Name "node"  # Check if process is running
```

# Available Actions (JSON response)

**Execute command:**
```json
{"action": "execute", "command": "your PowerShell command", "reasoning": "why"}
```

**Ask user (when uncertain):**
```json
{"action": "ask_user", "question": "...", "options": [...], "input_type": "choice"}
```

**Done:**
```json
{"action": "done", "message": "Deployed successfully on port X"}
```

**Failed:**
```json
{"action": "failed", "message": "Cannot deploy because..."}
```

# Remember: This is Windows!
- Use PowerShell commands
- Use backslashes in paths (or forward slashes, both usually work)
- No sudo needed
- npm, python, and docker work similarly to Linux if installed
"""
    
    def _build_linux_prompt(self) -> str:
        """Linux系统的提示词（原有的prompt）"""
        return """# Role
You are an intelligent, autonomous DevOps deployment agent. You have full access to a **Linux system** and can execute shell commands to deploy applications.

# Goal  
Deploy the given repository and ensure the application is running and accessible.
**Success criteria**: Application responds to HTTP requests with actual content.

# Your Capabilities
- Full access to a Linux system (local or remote)
- sudo available (password handled automatically if needed)
- Can execute ANY shell command
- Can install software, configure services, manage Docker, etc.
- Can ask the user for input when needed

# 🧠 THINK LIKE A LINUX DEVOPS EXPERT

## Deployment Strategies

### Strategy 1: Docker Compose (BEST for complex projects)
If you see `docker-compose.yml` or `docker-compose.yaml`:
```bash
cd ~/app && docker-compose up -d --build
```
- Handles ALL dependencies automatically
- Multi-service projects work out of the box
- Just verify with `docker-compose ps` and `curl`

### Strategy 2: Docker (if only Dockerfile)
If you see `Dockerfile` but no compose file:
```bash
cd ~/app && docker build -t myapp . && docker run -d -p <port>:<port> myapp
```

### Strategy 3: Traditional (if no Docker) - MANDATORY: Use Environment Isolation

**Python Projects:**
```bash
cd ~/app

# STEP 1: Create virtual environment (MANDATORY)
python3 -m venv venv

# STEP 2: Activate virtual environment (MANDATORY)
source venv/bin/activate

# STEP 3: Verify activation
which python  # Should show ~/app/venv/bin/python

# STEP 4: Install dependencies in isolated environment
pip install -r requirements.txt

# STEP 5: Run with venv Python
python app.py
# or for background:
nohup ./venv/bin/python app.py > app.log 2>&1 &
```

**Node.js Projects:**
```bash
cd ~/app

# STEP 1: Install dependencies locally (NEVER use -g)
npm install

# STEP 2: Build if needed
npm run build

# STEP 3: Start application
# Option A: Use npm scripts
npm start
# Option B: Use local PM2
npm install pm2  # Local, NOT global
npx pm2 start server.js --name myapp
# Option C: Background with nohup
nohup node server.js > app.log 2>&1 &
```

**Why environment isolation is mandatory:**
- ❌ `pip install flask` → System Python → conflicts with other projects
- ✅ `source venv/bin/activate && pip install flask` → Isolated → safe
- ❌ `npm install -g pm2` → Global → version conflicts
- ✅ `npm install pm2 && npx pm2` → Local → per-project isolation

### Strategy 4: Static Site
If it's just HTML/CSS/JS:
```bash
# Build if needed
npm run build

# Serve with Python (in venv if possible)
cd dist && python3 -m http.server 8080

# Or use npx serve (local)
npx serve -s dist -l 3000
```

# Linux Command Reference

### Package Management
```bash
# Update package lists
sudo apt-get update

# Install packages
sudo apt-get install -y package-name

# Check if command exists
which command-name
command -v command-name
```

### Process Management
```bash
# Run in background
nohup command > app.log 2>&1 &

# Check process
ps aux | grep process-name
pgrep -f process-name

# Kill process
pkill -f process-name
```

### Service Management
```bash
# Start/stop systemd service
sudo systemctl start service-name
sudo systemctl stop service-name
sudo systemctl status service-name
sudo systemctl enable service-name  # auto-start on boot
```

# Available Actions (JSON response)

**Execute command:**
```json
{"action": "execute", "command": "your command", "reasoning": "why"}
```

**Ask user:**
```json
{"action": "ask_user", "question": "...", "options": [...]}
```

**Done:**
```json
{"action": "done", "message": "Deployed successfully"}
```

**Failed:**
```json
{"action": "failed", "message": "Cannot deploy because..."}
```
"""
    
    def _build_macos_prompt(self) -> str:
        """macOS系统的提示词（类似Linux但有些差异）"""
        return """# Role
You are an intelligent deployment agent for **macOS systems**. You can execute shell commands to deploy applications.

# Goal  
Deploy the given repository on this Mac and ensure the application is running.

# Your Capabilities
- Execute shell commands on macOS
- Can use homebrew for package installation
- Similar to Linux but with macOS-specific tools

# macOS Command Reference

### Package Management
```bash
# Homebrew (preferred on macOS)
brew install package-name
brew install node
brew install python@3.11

# Check if command exists
which command-name
```

### Process Management
```bash
# Run in background (same as Linux)
nohup command > app.log 2>&1 &

# macOS-specific service management
launchctl start service-name
launchctl stop service-name
```

### Path Handling
```bash
# Home directory
~/

# Applications
/Applications/
```

## Deployment Strategies (MANDATORY: Use Environment Isolation)

### Strategy 1: Docker Desktop (Recommended)
```bash
cd ~/app
docker-compose up -d --build
# or
docker build -t myapp . && docker run -d -p 3000:3000 myapp
```

### Strategy 2: Python Projects - MANDATORY Virtual Environment
```bash
cd ~/app

# STEP 1: Create virtual environment (MANDATORY)
python3 -m venv venv

# STEP 2: Activate (MANDATORY)
source venv/bin/activate

# STEP 3: Verify activation
which python  # Should show ~/app/venv/bin/python

# STEP 4: Install dependencies
pip install -r requirements.txt

# STEP 5: Run application
python app.py
# or background:
nohup ./venv/bin/python app.py > app.log 2>&1 &
```

### Strategy 3: Node.js Projects - MANDATORY Local Dependencies
```bash
cd ~/app

# STEP 1: Install locally (NEVER use -g)
npm install

# STEP 2: Build if needed
npm run build

# STEP 3: Start
npm start
# or with local PM2:
npm install pm2
npx pm2 start server.js
```

**Why environment isolation is mandatory:**
- ❌ System-wide installs → version conflicts between projects
- ✅ Virtual environments → isolated, reproducible, safe

# Available Actions (JSON response)

**Execute command:**
```json
{"action": "execute", "command": "your command", "reasoning": "why"}
```

**Ask user:**
```json
{"action": "ask_user", "question": "...", "options": [...]}
```

**Done:**
```json
{"action": "done", "message": "Deployed successfully"}
```
"""

    def _build_prompt(self, context: dict) -> str:
        """Build the prompt for the LLM agent."""
        
        # 检测目标操作系统
        target_os = self._detect_target_os(context)
        
        # 用户交互说明
        user_interaction_guide = """
# 🗣️ User Interaction (IMPORTANT!)
You can ask the user for input when you encounter:
- **Multiple choices**: Different deployment options (dev/prod mode, ports, etc.)
- **Missing information**: Environment variables, configuration values
- **Confirmation needed**: Before risky operations (deleting data, overwriting)
- **Error recovery**: When stuck, ask user for guidance

To ask user, use action="ask_user" with this format:
```json
{
  "action": "ask_user",
  "question": "Clear question for the user",
  "options": ["Option 1", "Option 2", "Option 3"],  
  "input_type": "choice",
  "category": "decision",
  "context": "Additional context to help user decide",
  "default": "Option 1",
  "reasoning": "Why you need user input"
}
```

**input_type options:**
- "choice": User selects from options (can also input custom value)
- "text": Free text input
- "confirm": Yes/No confirmation
- "secret": Sensitive input (password, API key)

**category options:**
- "decision": Deployment choices (port, mode, entry point)
- "confirmation": Confirm risky operations
- "information": Need additional info (env vars)
- "error_recovery": Stuck and need user help

**When to ask user (主动询问):**
1. Multiple npm scripts available → Ask which to use
2. Unclear which port the app uses → Ask user
3. Need environment variables → Ask for values
4. Before `rm -rf` on existing deployment → Confirm
5. Deployment keeps failing → Ask user for guidance
"""

        # 根据目标OS构建系统提示词
        system_prompt = self._build_os_specific_prompt(target_os)
        
        # 添加用户交互指南到prompt
        system_prompt += "\n\n" + user_interaction_guide

        # 构建当前状态（使用智能提取后的历史）
        state = {
            "repo_url": context.get("repo_url"),
            "server": {
                "target": context.get("ssh_target"),
                "os": context.get("remote_host", {}).get("os_release") if context.get("remote_host") else "Linux",
            },
            "command_history": self._format_command_history(self.history[-10:]),  # 最近10条，格式化后
        }
        
        # 添加用户交互历史（如果有）
        if self.user_interactions:
            state["user_interactions"] = self.user_interactions[-5:]  # 最近5次用户交互
        
        # 组合最终 prompt
        parts = [system_prompt, "\n---\n"]
        
        # 添加过去的部署经验（如果有）
        if self.experience_retriever:
            try:
                project_type = context.get("project_type")
                framework = context.get("framework")
                
                # 构建查询：使用最近的命令输出或错误信息作为语义搜索条件
                query = None
                if self.history:
                    last_action = self.history[-1]
                    # 使用最近命令的输出作为查询（可能包含错误信息）
                    output = last_action.get("output") or last_action.get("result", "")
                    if isinstance(output, str) and len(output) > 20:
                        query = output[:500]  # 限制长度
                
                experiences_text = self.experience_retriever.get_formatted_experiences(
                    project_type=project_type,
                    framework=framework,
                    query=query,
                    max_results=10,
                    max_length=2000
                )
                if experiences_text:
                    parts.append(experiences_text)
                    parts.append("\n---\n")
            except Exception as e:
                logger.warning(f"Failed to retrieve experiences: {e}")
        
        # 添加部署计划上下文（如果有）
        plan_context = self._get_plan_context_for_prompt()
        if plan_context:
            parts.append(plan_context)
            parts.append("\n---\n")
        
        # 添加预分析的仓库上下文
        if "repo_analysis" in context:
            parts.append("# Pre-Analyzed Repository Context")
            parts.append(context["repo_analysis"])
            parts.append("\n---\n")
        
        parts.append("# Current Deployment State")
        parts.append(f"```json\n{json.dumps(state, indent=2, ensure_ascii=False)}\n```")
        
        # 如果有最近的用户交互，提醒 LLM
        if self.user_interactions:
            last_interaction = self.user_interactions[-1]
            parts.append(f"\n⚠️ User just responded: \"{last_interaction['user_response']}\" to your question about: \"{last_interaction['question'][:50]}...\"")
            parts.append("Use this information to proceed!")
        
        parts.append("\nBased on the above information, decide your next action. Respond with JSON only.")

        return "\n".join(parts)

    def _format_command_history(self, history: List[dict]) -> List[dict]:
        """
        格式化命令历史，使用提取后的输出而非完整输出

        Args:
            history: 原始历史记录列表

        Returns:
            格式化后的历史记录，适合发送给LLM
        """
        formatted = []
        for entry in history:
            # 构建精简的历史条目
            formatted_entry = {
                "iteration": entry.get("iteration"),
                "command": entry.get("command"),
                "success": entry.get("success"),
                "exit_code": entry.get("exit_code"),
            }

            # 添加提取后的输出摘要
            if "output_summary" in entry:
                formatted_entry["summary"] = entry["output_summary"]

            # 如果有关键信息，添加
            if entry.get("key_info"):
                formatted_entry["key_info"] = entry["key_info"]

            # 如果失败且有错误上下文，添加
            if not entry.get("success") and entry.get("error_context"):
                formatted_entry["error"] = entry["error_context"]

            formatted.append(formatted_entry)

        return formatted

    # ========== 规划阶段方法 ==========
    
    def _build_planning_prompt(self, context: dict) -> str:
        """构建规划阶段的 prompt"""
        repo_analysis = context.get("repo_analysis", "No repository analysis available.")
        project_type = context.get("project_type", "unknown")
        framework = context.get("framework", "unknown")
        deploy_dir = context.get("deploy_dir", "~/app")
        
        # 判断是本地还是远程部署
        is_local = context.get("mode") == "local"
        if is_local:
            target_info = f"Local machine ({context.get('local_host', {}).get('os_name', 'Unknown OS')})"
        else:
            target_info = context.get("ssh_target", "Remote server")
        
        prompt = f"""# Role
You are a DevOps deployment planner. Analyze the repository and create a structured deployment plan.

# Input
- Repository: {context.get("repo_url")}
- Deploy Directory: {deploy_dir}
- Target: {target_info}
- Project Type: {project_type}
- Framework: {framework}

# Repository Analysis
{repo_analysis}

# Task
Create a deployment plan. Think carefully about:
1. What deployment strategy is best? (Docker if Dockerfile exists, traditional otherwise)
2. What components need to be installed? (Node.js, Python, Nginx, etc.)
3. What are the exact steps to deploy this project?
4. What could go wrong? (missing env files, build errors, etc.)

Output a JSON object with this exact structure:
```json
{{
  "strategy": "docker-compose|docker|traditional|static",
  "components": ["list", "of", "required", "components"],
  "steps": [
    {{
      "id": 1,
      "name": "Short step name",
      "description": "What this step does and why",
      "category": "prerequisite|setup|build|deploy|verify",
      "estimated_commands": ["command1", "command2"],
      "success_criteria": "How to verify this step succeeded",
      "depends_on": []
    }}
  ],
  "risks": ["Potential risk 1", "Potential risk 2"],
  "notes": ["Important note 1"],
  "estimated_time": "5-10 minutes"
}}
```

# Rules
1. Choose the SIMPLEST strategy that works:
   - If docker-compose.yml exists → use "docker-compose"
   - If only Dockerfile exists → use "docker"
   - If neither exists → use "traditional" or "static"
2. Include ALL necessary steps (install dependencies, configure, build, deploy, verify)
3. Each step should be atomic and independently verifiable
4. Always include a final "verify" step to confirm deployment works
5. Identify risks from repository analysis (e.g., missing .env, syntax errors in configs)
6. Order steps by dependencies

# 🔒 CRITICAL: Environment Isolation (MANDATORY)
7. For "traditional" strategy, you MUST include environment isolation steps:
   - **Python projects**: MUST create and activate virtual environment BEFORE pip install
     Example step: "Create Python virtual environment (venv)"
   - **Node.js projects**: MUST use local dependencies (npm install, NOT npm install -g)
     Example step: "Install Node.js dependencies locally"
   - **Docker projects**: Already isolated, no additional steps needed
8. The environment isolation step should be in "setup" category and come BEFORE dependency installation
9. Example steps for Python project:
   - Step 1 (setup): "Create virtual environment" → python -m venv venv
   - Step 2 (setup): "Activate virtual environment and install dependencies" → source venv/bin/activate && pip install -r requirements.txt
10. Example steps for Node.js project:
   - Step 1 (setup): "Install local dependencies" → npm install (NEVER use -g)

# Category Definitions
- prerequisite: Install required software (Node.js, Docker, etc.)
- setup: Clone repo, configure environment, copy files
- build: Compile, bundle, or build the application
- deploy: Start services, configure web server
- verify: Test that deployment is working

Output ONLY valid JSON, no markdown code fence, no explanation."""

        return prompt

    def _create_deployment_plan(
        self,
        context: dict,
        repo_context: Optional["RepoContext"] = None,
    ) -> Optional[DeploymentPlan]:
        """
        让 LLM 生成部署计划。

        Args:
            context: 部署上下文（主机信息、仓库URL等）
            repo_context: 仓库分析结果

        Returns:
            DeploymentPlan 或 None（如果生成失败）
        """
        prompt = self._build_planning_prompt(context)

        # Use provider to generate plan (use temperature 0.0 for consistency)
        # Temporarily override temperature
        original_temp = self.llm_provider.temperature
        self.llm_provider.temperature = 0.0

        text = self.llm_provider.generate_response(
            prompt=prompt,
            response_format="json",
            timeout=self.planning_timeout,
            max_retries=3
        )

        # Restore original temperature
        self.llm_provider.temperature = original_temp

        if not text:
            logger.error("No response from LLM during planning")
            return None

        return self._parse_plan(text)

    def _parse_plan(self, llm_response: str) -> Optional[DeploymentPlan]:
        """解析 LLM 返回的 JSON 计划"""
        try:
            # 清理可能的 markdown 代码块
            text = llm_response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            data = json.loads(text)
            
            # 解析步骤
            steps = []
            for step_data in data.get("steps", []):
                step = DeploymentStep(
                    id=step_data.get("id", len(steps) + 1),
                    name=step_data.get("name", "Unnamed step"),
                    description=step_data.get("description", ""),
                    category=step_data.get("category", "setup"),
                    estimated_commands=step_data.get("estimated_commands", []),
                    success_criteria=step_data.get("success_criteria", ""),
                    depends_on=step_data.get("depends_on", []),
                )
                steps.append(step)
            
            plan = DeploymentPlan(
                strategy=data.get("strategy", "traditional"),
                components=data.get("components", []),
                steps=steps,
                risks=data.get("risks", []),
                notes=data.get("notes", []),
                estimated_time=data.get("estimated_time", "unknown"),
            )
            
            return plan
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse deployment plan: {e}")
            logger.debug(f"Raw response: {llm_response[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing plan: {e}")
            return None

    def _display_plan(self, plan: DeploymentPlan) -> None:
        """在控制台展示计划供用户审查"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("📋 DEPLOYMENT PLAN")
        logger.info("=" * 60)
        logger.info("")
        logger.info(f"Strategy: {plan.strategy.upper()}")
        logger.info(f"Components: {', '.join(plan.components) if plan.components else 'None'}")
        logger.info(f"Estimated Time: {plan.estimated_time}")
        logger.info("")
        
        # 显示步骤
        logger.info("Steps:")
        for step in plan.steps:
            category_emoji = {
                "prerequisite": "🔧",
                "setup": "📦",
                "build": "🏗️",
                "deploy": "🚀",
                "verify": "✅",
            }.get(step.category, "•")
            logger.info(f"  {step.id}. {category_emoji} [{step.category.upper()}] {step.name}")
            if step.description:
                logger.info(f"      {step.description}")
        
        # 显示风险
        if plan.risks:
            logger.info("")
            logger.info("⚠️  Identified Risks:")
            for risk in plan.risks:
                logger.info(f"  - {risk}")
        
        # 显示注意事项
        if plan.notes:
            logger.info("")
            logger.info("📝 Notes:")
            for note in plan.notes:
                logger.info(f"  - {note}")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("")

    def _ask_plan_approval(self, plan: DeploymentPlan) -> InteractionResponse:
        """询问用户是否批准部署计划"""
        # 构建选项
        options = [
            "Yes, proceed with this plan",
            "No, cancel deployment",
        ]
        
        # 构建上下文信息
        context_info = f"Strategy: {plan.strategy}\nSteps: {len(plan.steps)}\nEstimated: {plan.estimated_time}"
        
        request = InteractionRequest(
            question="Do you want to proceed with this deployment plan?",
            input_type=InputType.CHOICE,
            options=options,
            category=QuestionCategory.CONFIRMATION,
            context=context_info,
            default="Yes, proceed with this plan",
            allow_custom=True,
        )
        
        response = self.interaction_handler.ask(request)
        
        # 如果用户选择取消，标记为 cancelled
        if response.value and "No" in response.value:
            response.cancelled = True
        
        return response

    def _get_plan_context_for_prompt(self) -> str:
        """获取计划上下文用于执行阶段的 prompt"""
        if not self.current_plan:
            return ""
        
        plan = self.current_plan
        total_steps = len(plan.steps)
        
        # 构建计划概览
        lines = [
            "# 📋 Deployment Plan (Follow This!)",
            f"Strategy: {plan.strategy}",
            f"Progress: Step {self.current_plan_step + 1} of {total_steps}",
            "",
            "## Steps Overview:",
        ]
        
        for step in plan.steps:
            status = "✅" if step.id <= self.current_plan_step else ("🔄" if step.id == self.current_plan_step + 1 else "⬜")
            lines.append(f"  {status} {step.id}. {step.name}")
        
        # 当前步骤详情
        if self.current_plan_step < total_steps:
            current = plan.steps[self.current_plan_step]
            lines.extend([
                "",
                f"## 🎯 Current Step: {current.name}",
                f"Description: {current.description}",
                f"Category: {current.category}",
                f"Success Criteria: {current.success_criteria}",
            ])
            if current.estimated_commands:
                lines.append("Suggested Commands:")
                for cmd in current.estimated_commands:
                    lines.append(f"  - {cmd}")
        
        # 风险提醒
        if plan.risks:
            lines.extend(["", "## ⚠️ Known Risks:"])
            for risk in plan.risks:
                lines.append(f"  - {risk}")
        
        lines.append("")
        return "\n".join(lines)

    def _advance_plan_step(self) -> None:
        """推进到计划的下一步"""
        if self.current_plan and self.current_plan_step < len(self.current_plan.steps):
            self.current_plan_step += 1
            
            # 更新日志
            if "plan_execution" in self.deployment_log:
                self.deployment_log["plan_execution"]["current_step"] = self.current_plan_step

    def _mark_step_completed(self, step_id: int) -> None:
        """标记步骤为已完成"""
        if "plan_execution" in self.deployment_log:
            if step_id not in self.deployment_log["plan_execution"]["completed_steps"]:
                self.deployment_log["plan_execution"]["completed_steps"].append(step_id)


class DeploymentPlanner:
    """
    独立的部署计划生成器
    
    只负责生成部署计划，不负责执行。
    用于配合 DeploymentOrchestrator 使用。
    """
    
    def __init__(
        self,
        config: LLMConfig,
        planning_timeout: int = 60,
    ) -> None:
        if not config.api_key:
            raise ValueError("Planner requires an API key")
        self.config = config
        self.planning_timeout = planning_timeout

        # Initialize LLM provider
        from .base import create_llm_provider
        self.llm_provider = create_llm_provider(config)
        logger.info("Planner using LLM provider: %s (model: %s)", config.provider, config.model)

        # Keep for backward compatibility
        self.session = requests.Session()
        self._setup_proxy()

        self.base_endpoint = config.endpoint or (
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
        )
    
    def _setup_proxy(self) -> None:
        """设置代理"""
        import os
        proxy = self.config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            logger.debug("Planner using proxy: %s", proxy)
    
    def create_plan(
        self,
        repo_url: str,
        deploy_dir: str,
        host_info: dict,
        repo_analysis: Optional[str] = None,
        project_type: Optional[str] = None,
        framework: Optional[str] = None,
        is_local: bool = False,
    ) -> Optional[DeploymentPlan]:
        """
        生成部署计划
        
        Args:
            repo_url: 仓库 URL
            deploy_dir: 部署目录
            host_info: 主机信息
            repo_analysis: 仓库分析结果（prompt 格式）
            project_type: 项目类型
            framework: 框架
            is_local: 是否本地部署
            
        Returns:
            DeploymentPlan 或 None
        """
        import time
        
        # 构建上下文
        context = {
            "repo_url": repo_url,
            "deploy_dir": deploy_dir,
            "project_type": project_type or "unknown",
            "framework": framework or "unknown",
            "repo_analysis": repo_analysis or "No repository analysis available.",
            "mode": "local" if is_local else "remote",
        }
        
        if is_local:
            context["local_host"] = host_info
        else:
            context["host_info"] = host_info  # 完整的 host_info 字典
            context["ssh_target"] = host_info.get("target", "Remote server")
        
        prompt = self._build_planning_prompt(context)

        # Use provider to generate plan (use temperature 0.0 for consistency)
        original_temp = self.llm_provider.temperature
        self.llm_provider.temperature = 0.0

        text = self.llm_provider.generate_response(
            prompt=prompt,
            response_format="json",
            timeout=self.planning_timeout,
            max_retries=3
        )

        # Restore original temperature
        self.llm_provider.temperature = original_temp

        if not text:
            logger.error("No response from LLM during planning")
            return None

        return self._parse_plan(text)
    
    def _build_planning_prompt(self, context: dict) -> str:
        """构建规划阶段的 prompt"""
        import json
        
        repo_analysis = context.get("repo_analysis", "No repository analysis available.")
        project_type = context.get("project_type", "unknown")
        framework = context.get("framework", "unknown")
        deploy_dir = context.get("deploy_dir", "~/app")
        
        is_local = context.get("mode") == "local"
        if is_local:
            host_info = context.get('local_host', {})
            os_name = host_info.get('os_name', 'Unknown OS')
            os_release = host_info.get('os_release', 'Unknown version')
            tools = host_info.get('available_tools', {})
            
            target_info = f"Local machine ({os_name} - {os_release})"
            
            # 构建已安装工具列表
            installed_tools = [k for k, v in tools.items() if v]
            tools_info = f"\nInstalled tools: {', '.join(installed_tools) if installed_tools else 'none detected'}"
            
            # 构建完整的主机信息
            host_details = f"""
# Target Environment
- Platform: {target_info}
- Architecture: {host_info.get('architecture', 'unknown')}
- Kernel: {host_info.get('kernel', 'unknown')}
{tools_info}

**Environment Detection**:
- Running in Container: {'Yes (Docker-in-Docker limitations apply!)' if host_info.get('is_container') else 'No'}
- Init System: {'systemd' if host_info.get('has_systemd') else 'non-systemd (use service/init.d commands)'}
- Has Docker: {'Yes' if tools.get('docker') else 'No'}
- Has Git: {'Yes' if tools.get('git') else 'No'}
- Has Node.js: {'Yes' if tools.get('node') else 'No'}
- Has Python: {'Yes' if tools.get('python3') else 'No'}

**IMPORTANT**: If running in container AND project requires Docker, consider using 'traditional' strategy instead!
"""
        else:
            # SSH 远程模式
            host_info = context.get('host_info', {})
            target_info = context.get("ssh_target", "Remote server")
            
            # 提取远程主机信息
            os_release = host_info.get('os_release', 'Unknown')
            kernel = host_info.get('kernel', 'Unknown')
            arch = host_info.get('architecture', 'Unknown')
            is_container = host_info.get('is_container', False)
            has_systemd = host_info.get('has_systemd', False)
            
            host_details = f"""
# Target Environment
- Platform: {target_info}
- OS: {os_release}
- Kernel: {kernel}
- Architecture: {arch}

**Environment Detection**:
- Running in Container: {'Yes (Docker-in-Docker limitations apply!)' if is_container else 'No'}
- Init System: {'systemd' if has_systemd else 'non-systemd (use service/init.d commands)'}

**IMPORTANT**: If running in container AND project requires Docker, consider using 'traditional' strategy instead!
"""
        
        prompt = f"""# Role
You are a DevOps deployment planner. Analyze the repository and create a structured deployment plan.

# Input
- Repository: {context.get("repo_url")}
- Deploy Directory: {deploy_dir}
- Project Type: {project_type}
- Framework: {framework}

{host_details}

# Repository Analysis
{repo_analysis}

# Task
Create a deployment plan. Think carefully about:
1. What deployment strategy is best? (Docker if Dockerfile exists, traditional otherwise)
2. What components need to be installed? (Node.js, Python, Nginx, etc.)
3. What are the exact steps to deploy this project?
4. What could go wrong? (missing env files, build errors, etc.)

Output a JSON object with this exact structure:
```json
{{
  "strategy": "docker-compose|docker|traditional|static",
  "components": ["list", "of", "required", "components"],
  "steps": [
    {{
      "id": 1,
      "name": "Short step name",
      "description": "What this step does and why",
      "category": "prerequisite|setup|build|deploy|verify",
      "estimated_commands": ["command1", "command2"],
      "success_criteria": "How to verify this step succeeded",
      "depends_on": []
    }}
  ],
  "risks": ["Potential risk 1", "Potential risk 2"],
  "notes": ["Important note 1"],
  "estimated_time": "5-10 minutes"
}}
```

# Rules
1. Choose the SIMPLEST strategy that works:
   - If docker-compose.yml exists → use "docker-compose"
   - If only Dockerfile exists → use "docker"
   - If neither exists → use "traditional" or "static"
   
2. **Docker-in-Docker Detection (CRITICAL for testing environments)**:
   - If target environment is a container (check for: no systemd at PID 1, /proc/1/cgroup contains 'docker')
   - AND project requires Docker (Dockerfile present)
   - THEN: Skip Docker installation OR use "traditional" strategy instead
   - Add this to risks: "Running in containerized environment - Docker-in-Docker may not work"

3. Include ALL necessary steps (install dependencies, configure, build, deploy, verify)
4. Each step should be atomic and independently verifiable
5. Always include a final "verify" step to confirm deployment works
6. Identify risks from repository analysis (e.g., missing .env, syntax errors in configs)
7. Order steps by dependencies
8. Make success_criteria specific and verifiable:
   - For installation steps: Command availability (e.g., "docker --version succeeds")
   - For service steps: Service status (e.g., "systemctl status shows active OR docker ps works")
   - Provide fallback criteria for non-systemd environments

# 🔒 CRITICAL: Environment Isolation (MANDATORY)
9. For "traditional" strategy, you MUST include environment isolation steps:
   - **Python projects**: MUST create and activate virtual environment BEFORE pip install
     Example step: "Create Python virtual environment (venv)"
   - **Node.js projects**: MUST use local dependencies (npm install, NOT npm install -g)
     Example step: "Install Node.js dependencies locally"
   - **Docker projects**: Already isolated, no additional steps needed
10. The environment isolation step should be in "setup" category and come BEFORE dependency installation
11. Example steps for Python project:
   - Step X (setup): "Create virtual environment" → python -m venv venv
   - Step X+1 (setup): "Activate virtual environment and install dependencies" → source venv/bin/activate && pip install -r requirements.txt
12. Example steps for Node.js project:
   - Step X (setup): "Install local dependencies" → npm install (NEVER use -g)

# Category Definitions
- prerequisite: Install required software (Node.js, Docker, etc.)
- setup: Clone repo, configure environment, copy files
- build: Compile, bundle, or build the application
- deploy: Start services, configure web server
- verify: Test that deployment is working

Output ONLY valid JSON, no markdown code fence, no explanation."""

        return prompt
    
    def _parse_plan(self, llm_response: str) -> Optional[DeploymentPlan]:
        """解析 LLM 返回的 JSON 计划"""
        try:
            text = llm_response.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            
            data = json.loads(text)
            
            steps = []
            for step_data in data.get("steps", []):
                step = DeploymentStep(
                    id=step_data.get("id", len(steps) + 1),
                    name=step_data.get("name", "Unnamed step"),
                    description=step_data.get("description", ""),
                    category=step_data.get("category", "setup"),
                    estimated_commands=step_data.get("estimated_commands", []),
                    success_criteria=step_data.get("success_criteria", ""),
                    depends_on=step_data.get("depends_on", []),
                )
                steps.append(step)
            
            plan = DeploymentPlan(
                strategy=data.get("strategy", "traditional"),
                components=data.get("components", []),
                steps=steps,
                risks=data.get("risks", []),
                notes=data.get("notes", []),
                estimated_time=data.get("estimated_time", "unknown"),
            )
            
            return plan
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse deployment plan: {e}")
            logger.debug(f"Raw response: {llm_response[:500]}")
            return None
        except Exception as e:
            logger.error(f"Error parsing plan: {e}")
            return None
    
    @staticmethod
    def display_plan(plan: DeploymentPlan) -> None:
        """在控制台展示计划供用户审查"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("📋 DEPLOYMENT PLAN")
        logger.info("=" * 60)
        logger.info("")
        logger.info(f"Strategy: {plan.strategy.upper()}")
        logger.info(f"Components: {', '.join(plan.components) if plan.components else 'None'}")
        logger.info(f"Estimated Time: {plan.estimated_time}")
        logger.info("")
        
        logger.info("Steps:")
        for step in plan.steps:
            category_emoji = {
                "prerequisite": "🔧",
                "setup": "📦",
                "build": "🏗️",
                "deploy": "🚀",
                "verify": "✅",
            }.get(step.category, "•")
            logger.info(f"  {step.id}. {category_emoji} [{step.category.upper()}] {step.name}")
            if step.description:
                logger.info(f"      {step.description}")
            if step.success_criteria:
                logger.info(f"      ✓ Success: {step.success_criteria}")
        
        if plan.risks:
            logger.info("")
            logger.info("⚠️  Identified Risks:")
            for risk in plan.risks:
                logger.info(f"  - {risk}")
        
        if plan.notes:
            logger.info("")
            logger.info("📝 Notes:")
            for note in plan.notes:
                logger.info(f"  - {note}")
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("")