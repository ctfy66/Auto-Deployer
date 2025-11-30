"""LLM provider interfaces and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol, TYPE_CHECKING

from ..config import LLMConfig

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from ..workflow import DeploymentRequest
    from ..analyzer import RepositoryInsights
    from ..ssh import RemoteHostFacts


@dataclass
class PlanStep:
    """Single action recommended by the LLM."""

    title: str
    action: str
    details: str | None = None
    command: str | None = None


@dataclass
class WorkflowPlan:
    """Ordered list of actions returned by the LLM."""

    steps: List[PlanStep]


@dataclass
class FailureAnalysis:
    """Suggested remediation when a step fails."""

    summary: str
    suggested_step: Optional[PlanStep] = None


class LLMProvider(Protocol):
    """Interface every concrete provider must implement."""

    def plan_deployment(
        self,
        request: "DeploymentRequest",
        insights: "RepositoryInsights",
        host_facts: Optional["RemoteHostFacts"] = None,
    ) -> WorkflowPlan:
        ...

    def analyze_failure(
        self,
        step: PlanStep,
        error_message: str,
        context: dict,
    ) -> Optional[FailureAnalysis]:
        ...


class DummyLLMProvider:
    """Fallback provider that returns a static plan."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def plan_deployment(
        self,
        request: "DeploymentRequest",
        insights: "RepositoryInsights",
        host_facts: Optional["RemoteHostFacts"] = None,
    ) -> WorkflowPlan:
        host_summary = (
            f"host={host_facts.hostname} ({host_facts.os_release})"
            if host_facts
            else "host=unknown"
        )
        steps = [
            PlanStep(
                title="Clone repository",
                action="noop",
                details=f"Would clone {request.repo_url} locally",
            ),
            PlanStep(
                title="Analyze project",
                action="noop",
                details=(
                    "Would inspect repo files and build deployment plan. "
                    f"Insights: languages={insights.languages or ['unknown']} "
                    f"hints={insights.deployment_hints or ['none']}"
                ),
            ),
            PlanStep(
                title="Connect to server",
                action="noop",
                details=(
                    f"Would connect to {request.username}@{request.host}:{request.port}"
                    f" ({host_summary})"
                ),
            ),
            PlanStep(
                title="Deploy application",
                action="remote:run",
                details="LLM would determine the actual command",
                command="echo 'Simulated deployment'",
            ),
        ]
        return WorkflowPlan(steps=steps)

    def analyze_failure(
        self,
        step: PlanStep,
        error_message: str,
        context: dict,
    ) -> Optional[FailureAnalysis]:
        summary = f"Retrying with noop after error: {error_message}"
        if step.action == "noop":
                return FailureAnalysis(summary=summary, suggested_step=None)
        return FailureAnalysis(
            summary=summary,
            suggested_step=PlanStep(
                title=f"Retry noop for {step.title}",
                action="noop",
                details="LLM fallback to noop",
            ),
        )


def create_llm_provider(config: LLMConfig) -> LLMProvider:
    provider_name = config.provider.lower()
    if provider_name in {"dummy", "local"}:
        return DummyLLMProvider(config)
    if provider_name == "openai":
        from .openai import OpenAILLMProvider

        return OpenAILLMProvider(config)
    if provider_name == "gemini":
        from .gemini import GeminiLLMProvider

        return GeminiLLMProvider(config)
    # Placeholder for future providers (Claude, etc.)
    return DummyLLMProvider(config)
