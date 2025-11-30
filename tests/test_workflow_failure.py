import tempfile
import unittest
from pathlib import Path

from auto_deployer.analyzer import RepositoryInsights
from auto_deployer.config import AppConfig
from auto_deployer.gitops.manager import GitCloneResult, GitRepositoryManager
from auto_deployer.llm.provider import FailureAnalysis, PlanStep, WorkflowPlan, LLMProvider
from auto_deployer.workspace.manager import WorkspaceManager
from auto_deployer.workflow import DeploymentRequest, DeploymentWorkflow
from auto_deployer.ssh import RemoteHostFacts, RemoteProbe


class StubGitManager(GitRepositoryManager):
    def clone_or_update(self, repo_url, target_dir):  # type: ignore[override]
        target_dir.mkdir(parents=True, exist_ok=True)
        return GitCloneResult(commit_sha="deadbeef")


class StubAnalyzer:
    def analyze(self, context) -> RepositoryInsights:  # type: ignore[override]
        return RepositoryInsights(
            source_dir=context.source_dir,
            languages=["python"],
            deployment_hints=["python-pip"],
            detected_files={"requirements.txt": True},
        )


class StubRemoteProbe(RemoteProbe):
    def collect(self, session):  # type: ignore[override]
        return RemoteHostFacts(
            hostname="stub",
            kernel="Linux",
            architecture="x86_64",
            os_release="StubOS",
            shell="/bin/bash",
        )


class StubLLMProvider(LLMProvider):
    def __init__(self) -> None:
        self.failure_calls = 0

    def plan_deployment(self, request, insights, host_facts=None) -> WorkflowPlan:
        return WorkflowPlan(
            steps=[PlanStep(title="Break", action="unsupported", details=None)]
        )

    def analyze_failure(self, step, error_message, context):
        self.failure_calls += 1
        return FailureAnalysis(
            summary="Switch to noop",
            suggested_step=PlanStep(title="Fallback", action="noop", details=None),
        )


class WorkflowFailureTests(unittest.TestCase):
    def test_llm_repair_suggests_new_step(self) -> None:
        config = AppConfig()
        workspace_dir = tempfile.TemporaryDirectory()
        workspace_manager = WorkspaceManager(Path(workspace_dir.name))
        stub_git = StubGitManager()
        stub_analyzer = StubAnalyzer()
        stub_probe = StubRemoteProbe()
        stub_llm = StubLLMProvider()

        workflow = DeploymentWorkflow(
            config=config,
            workspace=workspace_dir.name,
            workspace_manager=workspace_manager,
            analyzer=stub_analyzer,  # type: ignore[arg-type]
            git_manager=stub_git,
            remote_probe=stub_probe,
            llm_provider=stub_llm,
        )
        workflow._create_remote_session = lambda request: None  # type: ignore
        request = DeploymentRequest(
            repo_url="https://example.com/repo.git",
            host="example.com",
            port=22,
            username="ubuntu",
            auth_method="password",
            password="pw",
            key_path=None,
        )
        workflow.run_deploy(request)
        self.assertEqual(stub_llm.failure_calls, 1)


if __name__ == "__main__":
    unittest.main()
