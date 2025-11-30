"""OpenAI-based LLM provider."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

import requests

from ..config import LLMConfig
from .provider import (
    FailureAnalysis,
    LLMProvider,
    PlanStep,
    WorkflowPlan,
    DummyLLMProvider,
)
if TYPE_CHECKING:  # pragma: no cover
    from ..analyzer import RepositoryInsights
    from ..ssh import RemoteHostFacts
    from ..workflow import DeploymentRequest

logger = logging.getLogger(__name__)


class OpenAILLMProvider(LLMProvider):
    """LLM provider that talks to the OpenAI Chat Completions API."""

    def __init__(self, config: LLMConfig) -> None:
        if not config.api_key:
            raise ValueError("OpenAI provider requires an API key")
        if not config.model:
            raise ValueError("OpenAI provider requires a model name")
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }
        )
        self.endpoint = config.endpoint or "https://api.openai.com/v1/chat/completions"
        self._fallback = DummyLLMProvider(config)

    def plan_deployment(
        self,
        request: "DeploymentRequest",
        insights: "RepositoryInsights",
        host_facts: Optional["RemoteHostFacts"] = None,
    ) -> WorkflowPlan:
        prompt = self._render_plan_prompt(request, insights, host_facts)
        content = self._chat(prompt)
        if not content:
            return self._fallback.plan_deployment(request, insights, host_facts)
        try:
            payload = json.loads(content)
            steps = [
                PlanStep(
                    title=step.get("title", "Step"),
                    action=step.get("action", "remote:run"),
                    details=step.get("details"),
                    command=step.get("command") or step.get("details"),
                )
                for step in payload.get("steps", [])
            ]
            if not steps:
                raise ValueError("no steps returned")
            return WorkflowPlan(steps=steps)
        except Exception as exc:  # pragma: no cover - network parsing fallback
            logger.warning("Failed to parse LLM plan response: %s", exc)
            return self._fallback.plan_deployment(request, insights, host_facts)

    def analyze_failure(
        self,
        step: PlanStep,
        error_message: str,
        context: Dict[str, Any],
    ) -> Optional[FailureAnalysis]:
        prompt = self._render_failure_prompt(step, error_message, context)
        content = self._chat(prompt)
        if not content:
            return self._fallback.analyze_failure(step, error_message, context)
        try:
            payload = json.loads(content)
            summary = payload.get("summary", "No summary")
            suggestion = payload.get("suggested_step")
            plan_step = None
            if suggestion:
                plan_step = PlanStep(
                    title=suggestion.get("title", step.title),
                    action=suggestion.get("action", step.action),
                    details=suggestion.get("details", step.details),
                    command=suggestion.get("command")
                    or suggestion.get("details")
                    or step.command,
                )
            return FailureAnalysis(summary=summary, suggested_step=plan_step)
        except Exception as exc:  # pragma: no cover - network parsing fallback
            logger.warning("Failed to parse LLM failure response: %s", exc)
            return self._fallback.analyze_failure(step, error_message, context)

    def _chat(self, prompt: str) -> Optional[str]:
        body = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert DevOps agent. Always reply with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        try:
            response = self.session.post(self.endpoint, json=body, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # pragma: no cover - network behaviour
            logger.error("OpenAI API call failed: %s", exc)
            return None

    def _render_plan_prompt(
        self,
        request: "DeploymentRequest",
        insights: "RepositoryInsights",
        host_facts: Optional["RemoteHostFacts"],
    ) -> str:
        return json.dumps(
            {
                "task": "plan",
                "repo_url": request.repo_url,
                "ssh_target": f"{request.username}@{request.host}:{request.port}",
                "insights": insights.to_payload(),
                "host_facts": host_facts.to_payload() if host_facts else None,
                "instructions": [
                    "Return a JSON object with a 'steps' array.",
                    {
                        "step_schema": {
                            "title": "short description",
                            "command": "shell command to execute remotely; include full command string",
                            "action": "optional hint such as remote:run or noop",
                            "details": "optional notes; not required",
                        }
                    },
                    "Prioritize idempotent remote commands. If local commands are required, set action to local:run and describe it in details.",
                ],
            },
            indent=2,
        )

    def _render_failure_prompt(
        self,
        step: PlanStep,
        error_message: str,
        context: Dict[str, Any],
    ) -> str:
        payload: Dict[str, Any] = {
            "task": "failure-analysis",
            "step": {
                "title": step.title,
                "action": step.action,
                "details": step.details,
                "command": step.command,
            },
            "error": error_message,
            "context": context,
            "response_schema": {
                "summary": "human readable diagnosis",
                "suggested_step": {
                    "title": "",
                    "action": "",
                    "details": "",
                },
            },
            "notes": "If no fix is possible, set suggested_step to null.",
        }
        return json.dumps(payload, indent=2)