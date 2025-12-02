"""High-level workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .analyzer import RepoAnalyzer, RepoContext
from .config import AppConfig
from .llm.agent import DeploymentAgent
from .ssh import RemoteHostFacts, RemoteProbe, SSHCredentials, SSHSession
from .utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class DeploymentRequest:
    """User-provided deployment request captured from the CLI."""

    repo_url: str
    host: str
    port: int
    username: str
    auth_method: str
    password: Optional[str]
    key_path: Optional[str]


class DeploymentWorkflow:
    """Coordinates deployment using the LLM Agent."""

    def __init__(
        self,
        config: AppConfig,
        workspace: str,
    ) -> None:
        self.config = config
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.remote_probe = RemoteProbe()

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

        try:
            # 使用 Agent 模式部署 - LLM 自行分析仓库
            self._run_agent_mode(request, host_facts, remote_session)
        finally:
            remote_session.close()

    def _run_agent_mode(
        self,
        request: DeploymentRequest,
        host_facts: Optional[RemoteHostFacts],
        session: SSHSession,
        repo_context: Optional[RepoContext] = None,
    ) -> None:
        """使用 Agent 模式：LLM 主导部署，使用预分析的仓库上下文。"""
        logger.info("🤖 Running in Agent mode - LLM will autonomously control deployment")
        
        if repo_context:
            logger.info("   (with pre-analyzed repository context)")
        
        agent = DeploymentAgent(self.config.llm, max_iterations=self.config.agent.max_iterations)
        success = agent.deploy(request, host_facts, session, repo_context)
        
        if success:
            logger.info("🎉 Agent deployment completed successfully!")
        else:
            logger.error("💥 Agent deployment failed")

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
