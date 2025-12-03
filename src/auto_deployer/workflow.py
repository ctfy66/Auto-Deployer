"""High-level workflow orchestration."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .analyzer import RepoAnalyzer, RepoContext
from .config import AppConfig
from .interaction import UserInteractionHandler, CLIInteractionHandler
from .llm.agent import DeploymentAgent
from .local import LocalSession, LocalProbe, LocalHostFacts
from .ssh import RemoteHostFacts, RemoteProbe, SSHCredentials, SSHSession
from .utils.logging import get_logger

logger = get_logger(__name__)


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


@dataclass
class LocalDeploymentRequest:
    """User-provided deployment request for local mode."""

    repo_url: str
    deploy_dir: Optional[str] = None  # 默认为 ~/app


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
        deploy_dir = request.deploy_dir or os.path.join(os.path.expanduser("~"), "app")
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
        """使用 Agent 模式本地部署。"""
        logger.info("🤖 Running in Local Agent mode")
        logger.info("   💬 Interactive mode enabled - Agent can ask for your input")
        
        if repo_context:
            logger.info("   (with pre-analyzed repository context)")
        
        # 尝试加载经验检索器
        experience_retriever = self._get_experience_retriever()
        if experience_retriever:
            logger.info("   🧠 Memory enabled - using past deployment experiences")
        
        agent = DeploymentAgent(
            self.config.llm,
            max_iterations=self.config.agent.max_iterations,
            interaction_handler=self.interaction_handler,
            experience_retriever=experience_retriever,
        )
        success = agent.deploy_local(request, host_facts, session, repo_context)
        
        if success:
            logger.info("🎉 Local deployment completed successfully!")
        else:
            logger.error("💥 Local deployment failed")

    def _run_agent_mode(
        self,
        request: DeploymentRequest,
        host_facts: Optional[RemoteHostFacts],
        session: SSHSession,
        repo_context: Optional[RepoContext] = None,
    ) -> None:
        """使用 Agent 模式：LLM 主导部署，使用预分析的仓库上下文。"""
        logger.info("🤖 Running in Agent mode - LLM will autonomously control deployment")
        logger.info("   💬 Interactive mode enabled - Agent can ask for your input")
        
        if repo_context:
            logger.info("   (with pre-analyzed repository context)")
        
        # 尝试加载经验检索器
        experience_retriever = self._get_experience_retriever()
        if experience_retriever:
            logger.info("   🧠 Memory enabled - using past deployment experiences")
        
        agent = DeploymentAgent(
            self.config.llm,
            max_iterations=self.config.agent.max_iterations,
            interaction_handler=self.interaction_handler,
            experience_retriever=experience_retriever,
        )
        success = agent.deploy(request, host_facts, session, repo_context)
        
        if success:
            logger.info("🎉 Agent deployment completed successfully!")
        else:
            logger.error("💥 Agent deployment failed")
    
    def _get_experience_retriever(self):
        """尝试获取经验检索器，如果依赖未安装则返回 None"""
        try:
            from .knowledge import ExperienceStore, ExperienceRetriever
            store = ExperienceStore()
            # 检查是否有已精炼的经验
            if store.refined_count() > 0:
                return ExperienceRetriever(store)
        except ImportError:
            # chromadb 或 sentence-transformers 未安装
            pass
        except Exception as e:
            logging.debug(f"Failed to load experience retriever: {e}")
        return None

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
