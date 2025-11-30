"""High-level workflow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import AppConfig
from .analyzer import RepositoryAnalyzer, RepositoryInsights
from .workspace import WorkspaceManager
from .gitops import GitRepositoryManager
from .llm.provider import LLMProvider, PlanStep, create_llm_provider
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
    """Coordinates planning and execution for a deployment run."""

    def __init__(
        self,
        config: AppConfig,
        workspace: str,
        max_retries: Optional[int] = None,
        *,
        workspace_manager: Optional[WorkspaceManager] = None,
        analyzer: Optional[RepositoryAnalyzer] = None,
        git_manager: Optional[GitRepositoryManager] = None,
        remote_probe: Optional[RemoteProbe] = None,
        llm_provider: Optional[LLMProvider] = None,
    ) -> None:
        self.config = config
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.default_retries = max_retries or config.deployment.default_max_retries
        self.workspace_manager = workspace_manager or WorkspaceManager(self.workspace)
        self.analyzer = analyzer or RepositoryAnalyzer()
        self.git_manager = git_manager or GitRepositoryManager()
        self.remote_probe = remote_probe or RemoteProbe()
        self.llm: LLMProvider = llm_provider or create_llm_provider(config.llm)

    def run_deploy(self, request: DeploymentRequest) -> None:
        logger.info("Preparing deployment for %s", request.repo_url)
        workspace_ctx = self.workspace_manager.prepare(request.repo_url)
        clone_info = self.git_manager.clone_or_update(
            request.repo_url, workspace_ctx.source_dir
        )
        self.workspace_manager.update_metadata(
            workspace_ctx,
            last_commit=clone_info.commit_sha,
        )
        logger.info(
            "Workspace ready at %s (commit %s)",
            workspace_ctx.source_dir,
            clone_info.commit_sha,
        )
        insights: RepositoryInsights = self.analyzer.analyze(workspace_ctx)
        logger.info(
            "Repository insights: languages=%s hints=%s",
            insights.languages,
            insights.deployment_hints,
        )
        remote_session = self._create_remote_session(request)
        host_facts: Optional[RemoteHostFacts] = None
        if remote_session:
            try:
                host_facts = self.remote_probe.collect(remote_session)
                logger.info(
                    "Remote host: %s (%s / %s)",
                    host_facts.hostname,
                    host_facts.os_release,
                    host_facts.kernel,
                )
            except Exception as exc:  # pragma: no cover - requires SSH server
                logger.warning("Failed to gather remote facts: %s", exc)

        plan = self.llm.plan_deployment(request, insights, host_facts)
        logger.info("LLM produced %d plan steps", len(plan.steps))

        try:
            for step in plan.steps:
                self._run_step(
                    step,
                    remote_session,
                    request,
                    insights,
                    host_facts,
                )
        finally:
            if remote_session:
                remote_session.close()

    def _run_step(
        self,
        step: PlanStep,
        session: Optional[SSHSession],
        request: DeploymentRequest,
        insights: RepositoryInsights,
        host_facts: Optional[RemoteHostFacts],
    ) -> None:
        current_step = step
        logger.info("→ %s", current_step.title)
        for attempt in range(1, self.default_retries + 1):
            try:
                logger.debug("Executing action: %s", current_step.action)
                self._execute_action(current_step, session)
                logger.info("✓ %s", current_step.title)
                return
            except Exception as exc:  # pragma: no cover - placeholder branch
                logger.warning(
                    "Step '%s' failed on attempt %d/%d: %s",
                    current_step.title,
                    attempt,
                    self.default_retries,
                    exc,
                )
                analysis = self.llm.analyze_failure(
                    current_step,
                    str(exc),
                    self._build_failure_context(
                        request, insights, host_facts, current_step, attempt
                    ),
                )
                if analysis:
                    logger.info("LLM analysis: %s", analysis.summary)
                    if analysis.suggested_step:
                        current_step = analysis.suggested_step
                        logger.info(
                            "Retrying with suggested step '%s' (%s)",
                            current_step.title,
                            current_step.action,
                        )
                        continue
        logger.error("Step '%s' exhausted retries", current_step.title)

    def _execute_action(self, step: PlanStep, session: Optional[SSHSession]) -> None:
        if step.command:
            if not session:
                raise RuntimeError(
                    "Remote session unavailable for command execution"
                )
            command = step.command.strip()
            if not command:
                raise RuntimeError("Command payload is empty")
            result = session.run(command)
            if not result.ok:
                raise RuntimeError(
                    f"Command '{command}' failed with {result.exit_status}: {result.stderr}"
                )
            logger.debug("Remote output: %s", result.stdout)
            return
        if step.action == "noop":
            return
        if step.action == "remote:run":
            if not session:
                raise RuntimeError("Remote session unavailable for command execution")
            command = step.details or "echo 'no command provided'"
            result = session.run(command)
            if not result.ok:
                raise RuntimeError(
                    f"Command '{command}' failed with {result.exit_status}: {result.stderr}"
                )
            logger.debug("Remote output: %s", result.stdout)
            return
        raise NotImplementedError(f"Unsupported action {step.action}")

    def _build_failure_context(
        self,
        request: DeploymentRequest,
        insights: RepositoryInsights,
        host_facts: Optional[RemoteHostFacts],
        step: PlanStep,
        attempt: int,
    ) -> dict:
        return {
            "attempt": attempt,
            "max_retries": self.default_retries,
            "repo_url": request.repo_url,
            "target_host": f"{request.username}@{request.host}:{request.port}",
            "step": {
                "title": step.title,
                "action": step.action,
                "details": step.details,
            },
            "insights": insights.to_payload(),
            "host_facts": host_facts.to_payload() if host_facts else None,
        }

    def _create_remote_session(self, request: DeploymentRequest) -> Optional[SSHSession]:
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
        except Exception as exc:  # pragma: no cover - requires SSH server
            logger.error("Failed to establish SSH connection: %s", exc)
            return None
