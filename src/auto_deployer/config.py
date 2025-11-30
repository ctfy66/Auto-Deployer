"""Configuration loading utilities for Auto-Deployer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

_DEFAULT_CONFIG_PATH = Path("config/default_config.json")


@dataclass
class LLMConfig:
    """Configuration for the LLM integration."""

    provider: str = "dummy"
    model: str = "planning-v0"
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    temperature: float = 0.0


@dataclass
class DeploymentConfig:
    """Settings related to deployment execution."""

    workspace_root: str = ".auto-deployer/workspace"
    default_max_retries: int = 3
    default_host: Optional[str] = None
    default_port: int = 22
    default_username: Optional[str] = None
    default_auth_method: Optional[str] = None
    default_password: Optional[str] = None
    default_key_path: Optional[str] = None


@dataclass
class AppConfig:
    """Top-level configuration."""

    llm: LLMConfig = field(default_factory=LLMConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AppConfig":
        llm_payload = payload.get("llm", {}) or {}
        deployment_payload = payload.get("deployment", {}) or {}
        return cls(
            llm=LLMConfig(**{**LLMConfig().__dict__, **llm_payload}),
            deployment=DeploymentConfig(
                **{**DeploymentConfig().__dict__, **deployment_payload}
            ),
        )


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load configuration from `path` or the default location."""

    candidate_paths = []
    if path:
        candidate_paths.append(Path(path))
    candidate_paths.append(_DEFAULT_CONFIG_PATH)

    for candidate in candidate_paths:
        if candidate.is_file():
            with candidate.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            config = AppConfig.from_dict(data)
            if not config.llm.api_key:
                provider_key = (
                    f"AUTO_DEPLOYER_{config.llm.provider.upper().replace('-', '_')}_API_KEY"
                )
                config.llm.api_key = os.getenv(provider_key) or os.getenv(
                    "AUTO_DEPLOYER_LLM_API_KEY"
                )
            return config

    raise FileNotFoundError(
        f"Could not find configuration file. Looked in: {', '.join(str(p) for p in candidate_paths)}"
    )
