"""High-level workflow orchestration."""

from __future__ import annotations

import os
import logging
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .analyzer import RepoAnalyzer, RepoContext
from .config import AppConfig
from .interaction import UserInteractionHandler, CLIInteractionHandler, InteractionRequest, InputType, QuestionCategory
from .llm.agent import DeploymentPlanner
from .local import LocalSession, LocalProbe, LocalHostFacts
from .ssh import RemoteHostFacts, RemoteProbe, SSHCredentials, SSHSession
from .utils.logging import get_logger

logger = get_logger(__name__)


def _get_repo_name(repo_url: str) -> str:
    """从仓库 URL 提取仓库名"""
    return repo_url.rstrip("/").split("/")[-1].replace(".git", "")


@dataclass
class DeploymentRequest:
    """User-provided deployment request captured from the CLI (SSH mode)."""

    repo_url: str
    host: str
    port: int
    username: str
    auth_method: str
    password: Optional[str]
    key_path: Optional[str]
    deploy_dir: Optional[str] = None  # 默认为 ~/<repo_name>


@dataclass
class LocalDeploymentRequest:
    """User-provided deployment request for local mode."""

    repo_url: str
    deploy_dir: Optional[str] = None  # 默认为 ~/<repo_name>


class DeploymentWorkflow:
    """Coordinates deployment using the LLM Agent."""

    def __init__(
        self,
        config: AppConfig,
        workspace: str,
        interaction_handler: Optional[UserInteractionHandler] = None,
    ) -> None:
        self.config = config
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.remote_probe = RemoteProbe()
        # 用户交互处理器 - 默认使用 CLI
        self.interaction_handler = interaction_handler or CLIInteractionHandler()

    def run_deploy(self, request: DeploymentRequest) -> None:
        """Run the deployment workflow using LLM Agent."""
        logger.info("Preparing deployment for %s", request.repo_url)
        
        # Step 1: 本地克隆并分析仓库
        logger.info("📦 Step 1: Analyzing repository locally...")
        repo_context = self._analyze_repository(request.repo_url)
        if repo_context:
            logger.info(
                "   Detected: %s project%s",
                repo_context.project_type or "unknown",
                f" ({repo_context.detected_framework})" if repo_context.detected_framework else "",
            )
            logger.info("   Found %d key files", len(repo_context.files))
        else:
            logger.warning("   Repository analysis failed, Agent will explore manually")
        
        # Step 2: 建立 SSH 连接
        logger.info("🔗 Step 2: Establishing SSH connection...")
        remote_session = self._create_remote_session(request)
        if not remote_session:
            logger.error("Cannot deploy without SSH session")
            return
        
        # Step 3: 收集远程主机信息
        host_facts: Optional[RemoteHostFacts] = None
        try:
            host_facts = self.remote_probe.collect(remote_session)
            logger.info(
                "   Remote host: %s (%s / %s)",
                host_facts.hostname,
                host_facts.os_release,
                host_facts.kernel,
            )
        except Exception as exc:
            logger.warning("   Failed to gather remote facts: %s", exc)

        try:
            # Step 4: 使用 Agent 模式部署
            logger.info("🤖 Step 3: Starting Agent deployment...")
            self._run_agent_mode(request, host_facts, remote_session, repo_context)
        finally:
            remote_session.close()

    def _analyze_repository(self, repo_url: str) -> Optional[RepoContext]:
        """Clone and analyze repository locally."""
        try:
            analyzer = RepoAnalyzer(workspace_dir=str(self.workspace))
            return analyzer.analyze(repo_url)
        except Exception as exc:
            logger.warning("Repository analysis failed: %s", exc)
            return None

    def run_local_deploy(self, request: LocalDeploymentRequest) -> None:
        """Run the deployment workflow locally (no SSH)."""
        import platform
        
        logger.info("Preparing LOCAL deployment for %s", request.repo_url)
        logger.info("🏠 Running on: %s (%s)", platform.node(), platform.system())
        
        # Step 1: 本地克隆并分析仓库
        logger.info("📦 Step 1: Analyzing repository locally...")
        repo_context = self._analyze_repository(request.repo_url)
        if repo_context:
            logger.info(
                "   Detected: %s project%s",
                repo_context.project_type or "unknown",
                f" ({repo_context.detected_framework})" if repo_context.detected_framework else "",
            )
            logger.info("   Found %d key files", len(repo_context.files))
        else:
            logger.warning("   Repository analysis failed, Agent will explore manually")
        
        # Step 2: 收集本地主机信息
        logger.info("🖥️  Step 2: Collecting local system info...")
        local_probe = LocalProbe()
        host_facts: Optional[LocalHostFacts] = None
        try:
            host_facts = local_probe.collect()
            logger.info(
                "   Local host: %s (%s)",
                host_facts.hostname,
                host_facts.os_release,
            )
            tools = []
            if host_facts.has_git:
                tools.append("git")
            if host_facts.has_node:
                tools.append("node")
            if host_facts.has_python3:
                tools.append("python")
            if host_facts.has_docker:
                tools.append("docker")
            logger.info("   Available tools: %s", ", ".join(tools) if tools else "none detected")
        except Exception as exc:
            logger.warning("   Failed to gather local facts: %s", exc)
        
        # Step 3: 创建本地会话
        # 获取默认部署目录（仓库名）
        repo_name = request.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        deploy_dir = request.deploy_dir or os.path.join(os.path.expanduser("~"), repo_name)
        logger.info("📁 Deploy directory: %s", deploy_dir)
        
        local_session = LocalSession(working_dir=os.path.expanduser("~"))
        local_session.connect()
        
        try:
            # Step 4: 使用 Agent 模式部署
            logger.info("🤖 Step 3: Starting Agent deployment (local mode)...")
            self._run_local_agent_mode(request, host_facts, local_session, repo_context)
        finally:
            local_session.close()

    def _run_local_agent_mode(
        self,
        request: LocalDeploymentRequest,
        host_facts: Optional[LocalHostFacts],
        session: LocalSession,
        repo_context: Optional[RepoContext] = None,
    ) -> None:
        """使用 Orchestrator 模式本地部署（plan-execute架构）。"""
        self._run_local_orchestrator_mode(request, host_facts, session, repo_context)
    
    def _run_local_orchestrator_mode(
        self,
        request: LocalDeploymentRequest,
        host_facts: Optional[LocalHostFacts],
        session: LocalSession,
        repo_context: Optional[RepoContext] = None,
    ) -> None:
        """使用 Orchestrator 模式本地部署（步骤独立执行）"""
        from .orchestrator import DeploymentOrchestrator, DeployContext
        
        logger.info("🤖 Running in Orchestrator mode (step-based execution)")
        logger.info("   💬 Interactive mode enabled - Agent can ask for your input")
        
        if repo_context:
            logger.info("   (with pre-analyzed repository context)")
        
        # 判断是否为 Windows
        is_windows = platform.system() == "Windows"
        
        # 1. 创建部署上下文
        repo_name = _get_repo_name(request.repo_url)
        deploy_dir = request.deploy_dir or os.path.join(os.path.expanduser("~"), repo_name)
        
        deploy_ctx = DeployContext(
            repo_url=request.repo_url,
            deploy_dir=deploy_dir,
            host_info=host_facts.to_payload() if host_facts else {"os_name": platform.system()},
            repo_analysis=repo_context.to_prompt_context() if repo_context else None,
            project_type=repo_context.project_type if repo_context else None,
            framework=repo_context.detected_framework if repo_context else None,
        )
        
        # 2. 生成部署计划
        logger.info("📋 Phase 1: Creating deployment plan...")
        planner = DeploymentPlanner(
            self.config.llm,
            planning_timeout=self.config.agent.planning_timeout,
        )
        
        plan = planner.create_plan(
            repo_url=request.repo_url,
            deploy_dir=deploy_dir,
            host_info=deploy_ctx.host_info,
            repo_analysis=deploy_ctx.repo_analysis,
            project_type=deploy_ctx.project_type,
            framework=deploy_ctx.framework,
            is_local=True,
        )
        
        if not plan:
            logger.error("Failed to create deployment plan")
            return
        
        # 3. 显示计划
        DeploymentPlanner.display_plan(plan)
        
        # 4. 用户确认（如果需要）
        if self.config.agent.require_plan_approval:
            if not self._ask_plan_approval(plan):
                logger.info("❌ User cancelled deployment")
                return
        
        # 5. 使用 Orchestrator 执行
        logger.info("🚀 Phase 2: Executing deployment plan...")
        
        # 优先使用配置中的 max_iterations_per_step，否则使用自动分配
        max_per_step = getattr(self.config.agent, 'max_iterations_per_step', None)
        if max_per_step is None:
            max_per_step = max(10, self.config.agent.max_iterations // max(len(plan.steps), 1))
        
        orchestrator = DeploymentOrchestrator(
            llm_config=self.config.llm,
            session=session,
            interaction_handler=self.interaction_handler,
            max_iterations_per_step=max_per_step,
            is_windows=is_windows,
            loop_detection_enabled=self.config.agent.loop_detection.enabled,
        )
        
        success = orchestrator.run(plan, deploy_ctx)
        
        if success:
            logger.info("🎉 Local deployment completed successfully!")
            # 自动提取经验
            if orchestrator.current_log_file:
                self._auto_extract_from_log(str(orchestrator.current_log_file))
        else:
            logger.error("💥 Local deployment failed")
    
    def _run_agent_mode(
        self,
        request: DeploymentRequest,
        host_facts: Optional[RemoteHostFacts],
        session: SSHSession,
        repo_context: Optional[RepoContext] = None,
    ) -> None:
        """使用 Orchestrator 模式：plan-execute分离架构。"""
        self._run_orchestrator_mode(request, host_facts, session, repo_context)
    
    def _run_orchestrator_mode(
        self,
        request: DeploymentRequest,
        host_facts: Optional[RemoteHostFacts],
        session: SSHSession,
        repo_context: Optional[RepoContext] = None,
    ) -> None:
        """使用 Orchestrator 模式部署（步骤独立执行）"""
        from .orchestrator import DeploymentOrchestrator, DeployContext
        
        logger.info("🤖 Running in Orchestrator mode (step-based execution)")
        logger.info("   💬 Interactive mode enabled - Agent can ask for your input")
        
        if repo_context:
            logger.info("   (with pre-analyzed repository context)")
        
        # 1. 创建部署上下文
        repo_name = _get_repo_name(request.repo_url)
        deploy_dir = request.deploy_dir or f"~/{repo_name}"
        
        # 构建主机信息字典
        if host_facts:
            host_info = host_facts.to_payload()
            host_info["target"] = f"{request.username}@{request.host}"
        else:
            host_info = {"target": f"{request.username}@{request.host}"}
        
        deploy_ctx = DeployContext(
            repo_url=request.repo_url,
            deploy_dir=deploy_dir,
            host_info=host_info,
            repo_analysis=repo_context.to_prompt_context() if repo_context else None,
            project_type=repo_context.project_type if repo_context else None,
            framework=repo_context.detected_framework if repo_context else None,
        )
        
        # 2. 生成部署计划
        logger.info("📋 Phase 1: Creating deployment plan...")
        planner = DeploymentPlanner(
            self.config.llm,
            planning_timeout=self.config.agent.planning_timeout,
        )
        
        plan = planner.create_plan(
            repo_url=request.repo_url,
            deploy_dir=deploy_dir,
            host_info=deploy_ctx.host_info,
            repo_analysis=deploy_ctx.repo_analysis,
            project_type=deploy_ctx.project_type,
            framework=deploy_ctx.framework,
            is_local=False,
        )
        
        if not plan:
            logger.error("Failed to create deployment plan")
            return
        
        # 3. 显示计划
        DeploymentPlanner.display_plan(plan)
        
        # 4. 用户确认（如果需要）
        if self.config.agent.require_plan_approval:
            if not self._ask_plan_approval(plan):
                logger.info("❌ User cancelled deployment")
                return
        
        # 5. 使用 Orchestrator 执行
        logger.info("🚀 Phase 2: Executing deployment plan...")
        
        # 优先使用配置中的 max_iterations_per_step，否则使用自动分配
        max_per_step = getattr(self.config.agent, 'max_iterations_per_step', None)
        if max_per_step is None:
            max_per_step = max(10, self.config.agent.max_iterations // max(len(plan.steps), 1))
        
        orchestrator = DeploymentOrchestrator(
            llm_config=self.config.llm,
            session=session,
            interaction_handler=self.interaction_handler,
            max_iterations_per_step=max_per_step,
            is_windows=False,
            loop_detection_enabled=self.config.agent.loop_detection.enabled,
        )
        
        success = orchestrator.run(plan, deploy_ctx)
        
        if success:
            logger.info("🎉 Deployment completed successfully!")
            # 自动提取经验
            if orchestrator.current_log_file:
                self._auto_extract_from_log(str(orchestrator.current_log_file))
        else:
            logger.error("💥 Deployment failed")
    
    
    def _ask_plan_approval(self, plan) -> bool:
        """询问用户是否批准部署计划"""
        request = InteractionRequest(
            question="Do you want to proceed with this deployment plan?",
            input_type=InputType.CHOICE,
            options=["Yes, proceed with this plan", "No, cancel deployment"],
            category=QuestionCategory.CONFIRMATION,
            context=f"Strategy: {plan.strategy}\nSteps: {len(plan.steps)}\nEstimated: {plan.estimated_time}",
            default="Yes, proceed with this plan",
            allow_custom=True,
        )
        
        response = self.interaction_handler.ask(request)
        
        if response.cancelled or (response.value and "No" in response.value):
            return False
        return True
    
    def _get_experience_retriever(self):
        """尝试获取经验检索器，如果依赖未安装则返回 None"""
        try:
            from .knowledge import ExperienceStore, ExperienceRetriever, init_preset_experiences
            store = ExperienceStore()
            
            # 初始化预置经验（只会添加不存在的）
            added = init_preset_experiences(store)
            if added > 0:
                logger.info(f"📦 Initialized {added} preset experiences")
            
            # 检查是否有任何经验（精炼的或原始的）
            total_experiences = store.refined_count() + store.raw_count()
            if total_experiences > 0:
                logger.info(f"📚 Loaded experience store: {store.refined_count()} refined, {store.raw_count()} raw")
                return ExperienceRetriever(store)
        except ImportError:
            # chromadb 或 sentence-transformers 未安装
            pass
        except Exception as e:
            logging.debug(f"Failed to load experience retriever: {e}")
        return None

    def _auto_extract_from_log(self, log_path: str) -> None:
        """部署成功后自动提取经验（仅代码提取，不用LLM精炼）"""
        try:
            from .knowledge import ExperienceStore, ExperienceExtractor
            
            extractor = ExperienceExtractor()
            experiences = extractor.extract_from_log(Path(log_path))
            
            if not experiences:
                return
            
            store = ExperienceStore()
            added = 0
            for exp in experiences:
                if not store.raw_exists(exp.id):
                    store.add_raw_experience(
                        id=exp.id,
                        content=exp.content,
                        metadata={
                            "project_type": exp.project_type or "unknown",
                            "framework": exp.framework or "",
                            "source_log": exp.source_log,
                            "timestamp": exp.timestamp,
                            "processed": "False",
                        }
                    )
                    added += 1
            
            if added > 0:
                logger.info(f"📥 Auto-extracted {added} experience(s) from this deployment")
                
        except ImportError:
            # chromadb/sentence-transformers 未安装，静默跳过
            pass
        except Exception as e:
            logger.debug(f"Auto-extract failed: {e}")

    def _create_remote_session(self, request: DeploymentRequest) -> Optional[SSHSession]:
        """Create an SSH session to the remote server."""
        try:
            creds = SSHCredentials(
                host=request.host,
                port=request.port,
                username=request.username,
                auth_method=request.auth_method,
                password=request.password,
                key_path=request.key_path,
            )
            creds.validate()
        except ValueError as exc:
            logger.error("Invalid SSH credentials: %s", exc)
            return None

        session = SSHSession(creds)
        try:
            session.connect()
            return session
        except Exception as exc:
            logger.error("Failed to establish SSH connection: %s", exc)
            return None
