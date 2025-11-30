"""Gemini-based LLM provider."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

import requests

from ..config import LLMConfig
from .provider import FailureAnalysis, LLMProvider, PlanStep, WorkflowPlan, DummyLLMProvider

if TYPE_CHECKING:  # pragma: no cover
    from ..analyzer import RepositoryInsights
    from ..ssh import RemoteHostFacts
    from ..workflow import DeploymentRequest

logger = logging.getLogger(__name__)


class GeminiLLMProvider(LLMProvider):
    """LLM provider that talks to the Gemini Generative Language API."""

    def __init__(self, config: LLMConfig) -> None:
        if not config.api_key:
            raise ValueError("Gemini provider requires an API key")
        if not config.model:
            raise ValueError("Gemini provider requires a model name")
        self.config = config
        self.session = requests.Session()
        # 支持代理配置（从环境变量或配置读取）
        import os
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
            logger.info("Using proxy: %s", proxy)
        self.base_endpoint = config.endpoint or (
            f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
        )
        self._fallback = DummyLLMProvider(config)

    def plan_deployment(
        self,
        request: "DeploymentRequest",
        insights: "RepositoryInsights",
        host_facts: Optional["RemoteHostFacts"] = None,
    ) -> WorkflowPlan:
        prompt = self._render_plan_prompt(request, insights, host_facts)
        content = self._generate(prompt)
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
            logger.warning("Failed to parse Gemini plan response: %s", exc)
            return self._fallback.plan_deployment(request, insights, host_facts)

    def analyze_failure(
        self,
        step: PlanStep,
        error_message: str,
        context: Dict[str, Any],
    ) -> Optional[FailureAnalysis]:
        prompt = self._render_failure_prompt(step, error_message, context)
        content = self._generate(prompt)
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
            logger.warning("Failed to parse Gemini failure response: %s", exc)
            return self._fallback.analyze_failure(step, error_message, context)

    def _generate(self, prompt: str) -> Optional[str]:
        url = f"{self.base_endpoint}?key={self.config.api_key}"
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt,
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": self.config.temperature,
                "responseMimeType": "application/json",
            },
        }
        try:
            response = self.session.post(url, json=body, timeout=30)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates") or []
            for candidate in candidates:
                parts = candidate.get("content", {}).get("parts", [])
                for part in parts:
                    text = part.get("text")
                    if text:
                        return text
            return None
        except Exception as exc:  # pragma: no cover - network behaviour
            logger.error("Gemini API call failed: %s", exc)
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
                            "command": "shell command executed remotely on the target server",
                            "action": "remote:run",
                            "details": "optional justification",
                        }
                    },
                    "CRITICAL RULES:",
                    "1. All commands run on the REMOTE server via SSH.",
                    "2. For git clone, use: rm -rf <dir> && git clone <url> <dir> to make it idempotent.",
                    "3. Do NOT use rsync, scp, or local-to-remote file transfer.",
                    "4. sudo is handled automatically, just write normal sudo commands.",
                    "5. Use python3 instead of python.",
                    "6. MUST start the application after setup using nohup or the deploy.sh script.",
                    "7. Check 'entry_points' in insights to find the correct entry file (e.g., app.py, deploy.sh).",
                    "8. Final step: verify the app is running with curl or process check.",
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
        return json.dumps(
            {
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
                        "command": "shell command",
                        "action": "optional hint",
                        "details": "optional notes",
                    },
                },
                "notes": "If no fix is possible, set suggested_step to null.",
            },
            indent=2,
        )