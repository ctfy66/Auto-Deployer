"""High-level workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

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
        max_retries: Optional[int] = None,
    ) -> None:
        self.config = config
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.default_retries = max_retries or config.deployment.default_max_retries
        self.remote_probe = RemoteProbe()

    def run_deploy(self, request: DeploymentRequest) -> None:
        """Run the deployment workflow using LLM Agent."""
        logger.info("Preparing deployment for %s", request.repo_url)
        
        # 建立 SSH 连接
        remote_session = self._create_remote_session(request)
        if not remote_session:
            logger.error("Cannot deploy without SSH session")
            return
        
        # 收集远程主机信息
        host_facts: Optional[RemoteHostFacts] = None
        try:
            host_facts = self.remote_probe.collect(remote_session)
            logger.info(
                "Remote host: %s (%s / %s)",
                host_facts.hostname,
                host_facts.os_release,
                host_facts.kernel,
            )
        except Exception as exc:
            logger.warning("Failed to gather remote facts: %s", exc)

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
    ) -> None:
        """使用 Agent 模式：LLM 全程主导部署，自行分析仓库。"""
        logger.info("🤖 Running in Agent mode - LLM will autonomously control deployment")
        agent = DeploymentAgent(self.config.llm, max_iterations=20)
        success = agent.deploy(request, host_facts, session)
        
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
