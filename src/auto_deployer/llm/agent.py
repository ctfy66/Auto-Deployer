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

if TYPE_CHECKING:
    from ..ssh import RemoteHostFacts
    from ..workflow import DeploymentRequest, LocalDeploymentRequest
    from ..ssh import SSHSession
    from ..local import LocalSession, LocalHostFacts
    from ..analyzer import RepoContext
    from ..knowledge import ExperienceRetriever

logger = logging.getLogger(__name__)


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
        
        # 日志目录
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "agent_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前部署的日志文件
        self.current_log_file: Optional[Path] = None
        self.deployment_log: dict = {}
        
        # 用户交互历史（发送给 LLM）
        self.user_interactions: List[dict] = []
        
        # 设置代理 - 优先使用配置文件，其次使用环境变量
        import os
        proxy = config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            logger.info("Agent using proxy: %s", proxy)
        
        self.base_endpoint = config.endpoint or (
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
        )
        
        # 执行历史
        self.history: List[dict] = []

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
        context = self._build_initial_context(request, host_facts, repo_context)
        
        # 记录初始上下文
        self.deployment_log["context"] = {
            "repo_url": context.get("repo_url"),
            "ssh_target": context.get("ssh_target"),
            "has_repo_analysis": repo_context is not None,
            "project_type": repo_context.project_type if repo_context else None,
            "framework": repo_context.detected_framework if repo_context else None,
        }
        
        for iteration in range(1, self.max_iterations + 1):
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
                    logger.info(f"   Reason: {action.reasoning}")
                
                # 执行命令
                result = self._execute_command(ssh_session, action.command)
                
                # 记录命令结果
                step_log["result"] = {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout[:2000] if result.stdout else "",
                    "stderr": result.stderr[:2000] if result.stderr else "",
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
        logger.info("   Deploy Dir:     %s", request.deploy_dir or "~/app")
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
        context = self._build_local_initial_context(request, host_facts, repo_context)
        
        # 记录初始上下文
        self.deployment_log["context"] = {
            "repo_url": context.get("repo_url"),
            "deploy_dir": request.deploy_dir or "~/app",
            "os": host_facts.os_name if host_facts else platform.system(),
            "has_repo_analysis": repo_context is not None,
            "project_type": repo_context.project_type if repo_context else None,
            "framework": repo_context.detected_framework if repo_context else None,
        }
        
        for iteration in range(1, self.max_iterations + 1):
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
                    logger.info(f"   Reason: {action.reasoning}")
                
                # 执行本地命令
                result = self._execute_local_command(local_session, action.command)
                
                # 记录命令结果
                step_log["result"] = {
                    "success": result.success,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout[:2000] if result.stdout else "",
                    "stderr": result.stderr[:2000] if result.stderr else "",
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
        repo_name = request.repo_url.split("/")[-1].replace(".git", "")
        filename = f"deploy_local_{repo_name}_{timestamp}.json"
        self.current_log_file = self.log_dir / filename
        
        self.deployment_log = {
            "mode": "local",
            "repo_url": request.repo_url,
            "target": f"local:{platform.node()}",
            "deploy_dir": request.deploy_dir or "~/app",
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
        repo_name = request.repo_url.split("/")[-1].replace(".git", "")
        filename = f"deploy_{repo_name}_{timestamp}.json"
        self.current_log_file = self.log_dir / filename
        
        self.deployment_log = {
            "repo_url": request.repo_url,
            "target": f"{request.username}@{request.host}:{request.port}",
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
        ctx = {
            "repo_url": request.repo_url,
            "deploy_dir": request.deploy_dir or "~/app",
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
            result = session.run(command, timeout=300)  # 本地命令给更长超时
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
        import time
        
        prompt = self._build_local_prompt(context)
        
        url = f"{self.base_endpoint}?key={self.config.api_key}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "responseMimeType": "application/json",
            },
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, json=body, timeout=60)
                
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                candidates = data.get("candidates") or []
                for candidate in candidates:
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text")
                        if text:
                            return self._parse_action(text)
                
                logger.error("No response from LLM")
                return AgentAction(action_type="failed", message="No LLM response")
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"LLM API call failed: {e}")
                return AgentAction(action_type="failed", message=str(e))
            except Exception as exc:
                logger.error(f"LLM API call failed: {exc}")
                return AgentAction(action_type="failed", message=str(exc))
        
        return AgentAction(action_type="failed", message="Rate limited after max retries")

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
- Deploy to: {context.get('deploy_dir', '~/app')}

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
- Deploy to: {context.get('deploy_dir', '~/app')}

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
3. Verify with curl: `curl -s http://localhost:<port>`
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
        import time
        
        prompt = self._build_prompt(context)
        
        url = f"{self.base_endpoint}?key={self.config.api_key}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "responseMimeType": "application/json",
            },
        }
        
        # 重试机制处理速率限制
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(url, json=body, timeout=60)
                
                # 处理速率限制
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)  # 30s, 60s, 90s
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                
                # 提取响应文本
                candidates = data.get("candidates") or []
                for candidate in candidates:
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text")
                        if text:
                            return self._parse_action(text)
                
                logger.error("No response from LLM")
                return AgentAction(action_type="failed", message="No LLM response")
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"LLM API call failed: {e}")
                return AgentAction(action_type="failed", message=str(e))
            except Exception as exc:
                logger.error(f"LLM API call failed: {exc}")
                return AgentAction(action_type="failed", message=str(exc))
        
        return AgentAction(action_type="failed", message="Rate limited after max retries")

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
            result = session.run(command, timeout=120)
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
        ctx = {
            "repo_url": request.repo_url,
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

    def _build_prompt(self, context: dict) -> str:
        """Build the prompt for the LLM agent."""
        
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

        # 构建系统提示词
        system_prompt = """# Role
You are an intelligent, autonomous DevOps deployment agent. You have full SSH access to a remote Linux server and can execute any shell commands to deploy applications.

# Goal  
Deploy the given repository and ensure the application is running and accessible.
**Success criteria**: Application responds to HTTP requests with actual content.

# Your Capabilities
- Full SSH access to a Linux server
- sudo available (password handled automatically)
- Can execute ANY shell command
- Can install software, configure services, manage Docker, etc.
- Can ask the user for input when needed

# 🧠 THINK LIKE AN EXPERT DEVOPS ENGINEER
You are NOT limited to a fixed deployment script. Analyze the project and **choose the best deployment strategy**:

## Strategy 1: Docker Compose (BEST for complex projects)
If you see `docker-compose.yml` or `docker-compose.yaml`:
```bash
cd ~/app && docker-compose up -d --build
```
- Handles ALL dependencies automatically
- Multi-service projects work out of the box
- Just verify with `docker-compose ps` and `curl`

## Strategy 2: Docker (if only Dockerfile)
If you see `Dockerfile` but no compose file:
```bash
cd ~/app && docker build -t myapp . && docker run -d -p <port>:<port> myapp
```

## Strategy 3: Traditional (if no Docker)
Only if no Docker files exist:
- Install dependencies (`pip install` / `npm install`)
- Start with process manager or nohup

## Strategy 4: Static Site
If it's just HTML/CSS/JS:
- Serve with nginx or python -m http.server

# 📋 Pre-Analyzed Repository Info
You have been given analyzed repository context below. Key things to look for:
- **Dockerfile / docker-compose.yml** → Use Docker!
- **config.py.example / .env.example** → Need to copy/configure first
- **Multiple entry points** → May need PM2 or supervisor
- **Complex dependencies** → Docker is your friend

# Available Actions (JSON response)

**Execute command:**
```json
{"action": "execute", "command": "your command", "reasoning": "why"}
```

**Ask user (when uncertain):**
```json
{"action": "ask_user", "question": "...", "options": [...], "input_type": "choice", "category": "decision"}
```

**Done:**
```json
{"action": "done", "message": "Deployed successfully on port X"}
```

**Failed:**
```json
{"action": "failed", "message": "Cannot deploy because..."}
```

# ⚠️ Critical Constraints
1. **Long-running commands BLOCK FOREVER** - Use `nohup ... &` or Docker `-d`
2. **Verification needs actual content** - Empty curl = failure
3. **Ask user when stuck** - Don't waste iterations on trial-and-error

# 🔧 Error Diagnosis & Self-Correction

**If you see `sudo: X incorrect password attempts`:**
ROOT CAUSE: sudo password is passed via stdin, but something else in your command also consumed stdin (pipes, heredoc, interactive input).
PRINCIPLE: When using sudo, ensure no other part of the command competes for stdin.
SOLUTION: Split into separate commands - first prepare data/download files, then run sudo on the result.

**If command seems to hang forever:**
ROOT CAUSE: You ran a blocking foreground process.
SOLUTION: Use background execution (`nohup ... &`, `... &`, or Docker `-d`).

# �️ Shell Best Practices

## Writing config files with sudo
✅ RECOMMENDED: Use `sudo bash -c` with heredoc inside single quotes:
```bash
sudo bash -c 'cat > /etc/nginx/sites-available/mysite <<EOF
server {
    listen 80;
    ...
}
EOF'
```
This keeps the heredoc inside bash's stdin, separate from sudo's password input.

❌ AVOID: `sudo tee <<EOF` or `echo "..." | sudo tee` (stdin conflicts with password)

## Downloading scripts that need sudo
❌ WRONG: `curl ... | sudo bash` (stdin conflict)
✅ CORRECT: `curl -o script.sh ... && sudo bash script.sh`

## Idempotent commands (safe to re-run)
- Use `ln -sf` instead of `ln -s` (force overwrite existing symlink)
- Use `mkdir -p` instead of `mkdir` (no error if exists)
- Use `rm -f` instead of `rm` (no error if not exists)
- Use `git clone` with check: `test -d /path || git clone ...`

## Nginx try_files for static sites
✅ CORRECT: `try_files $uri $uri/index.html /index.html;`
❌ WRONG: `try_files $uri /index.html;` (needs at least 2 args + fallback)

# �💡 Decision Making Guide
- See `docker-compose.yml`? → `docker-compose up -d` (DON'T pip install!)
- See `Dockerfile`? → `docker build && docker run`
- See `config.example`? → Copy it first, or ask user for values
- See complex project structure? → Docker is probably the answer
- Keep failing? → Ask user for guidance, don't just retry the same thing
"""

        # 构建当前状态
        state = {
            "repo_url": context.get("repo_url"),
            "server": {
                "target": context.get("ssh_target"),
                "os": context.get("remote_host", {}).get("os_release") if context.get("remote_host") else "Linux",
            },
            "command_history": self.history[-10:],  # 最近10条命令历史
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
                experiences_text = self.experience_retriever.get_formatted_experiences(
                    project_type=project_type,
                    framework=framework,
                    max_results=10,
                    max_length=2000
                )
                if experiences_text:
                    parts.append(experiences_text)
                    parts.append("\n---\n")
            except Exception as e:
                logger.warning(f"Failed to retrieve experiences: {e}")
        
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
