"""Configuration loading utilities for Auto-Deployer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

_DEFAULT_CONFIG_PATH = Path("config/default_config.json")

# Provider default configurations
# 提供商默认配置：当用户未指定 model 或 endpoint 时使用
PROVIDER_DEFAULTS = {
    "gemini": {
        "model": "gemini-2.5-flash",
        "endpoint": None  #自动生成 endpoint
    },
    "openai": {
        "model": "gpt-4o",
        "endpoint": "https://api.openai.com/v1"
    },
    "anthropic": {
        "model": "claude-3-5-sonnet-20241022",
        "endpoint": "https://api.anthropic.com/v1"
    },
    "claude": {  
        "model": "claude-3-5-sonnet-20241022",
        "endpoint": "https://api.anthropic.com/v1"
    },
    "deepseek": {
        "model": "deepseek-chat",
        "endpoint": "https://api.deepseek.com/v1"
    },
    "openrouter": {
        "model": "anthropic/claude-3.5-sonnet",
        "endpoint": "https://openrouter.ai/api/v1"
    },
    "openai-compatible": {
        "model": None,  # 依赖用户配置
        "endpoint": None  # 必须由用户指定
    },
    "custom": {  # openai-compatible 的别名
        "model": None,
        "endpoint": None
    }
}


@dataclass
class LLMConfig:
    """Configuration for the LLM integration."""

    provider: str = "dummy"
    model: str = "planning-v0"
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    temperature: float = 0.0
    proxy: Optional[str] = None  # 代理设置，如 "http://127.0.0.1:7890"


@dataclass
class AgentConfig:
    """Configuration for the deployment agent."""

    max_iterations: int = 180  # 总迭代次数（orchestrator 模式下会分配给各步骤）
    max_iterations_per_step: int = 30  # 每个步骤的最大迭代次数（orchestrator 模式专用）
    # 规划阶段配置
    enable_planning: bool = True           # 是否启用规划阶段
    require_plan_approval: bool = False    # 是否需要用户确认计划
    planning_timeout: int = 60             # 规划超时（秒）
    # 执行模式
    use_orchestrator: bool = True          # 使用新的 Orchestrator 模式（步骤独立执行）


@dataclass
class DeploymentConfig:
    """Settings related to deployment execution."""
    
    # 使用统一的 .auto-deployer 目录结构
    workspace_root: str = ".auto-deployer/workspace"  # 本地仓库分析
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
    agent: AgentConfig = field(default_factory=AgentConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AppConfig":
        llm_payload = payload.get("llm", {}) or {}
        agent_payload = payload.get("agent", {}) or {}
        deployment_payload = payload.get("deployment", {}) or {}
        return cls(
            llm=LLMConfig(**{**LLMConfig().__dict__, **llm_payload}),
            agent=AgentConfig(**{**AgentConfig().__dict__, **agent_payload}),
            deployment=DeploymentConfig(
                **{**DeploymentConfig().__dict__, **deployment_payload}
            ),
        )


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load configuration from `path` or the default location.
    
    Environment variables (higher priority than config file):
    - AUTO_DEPLOYER_LLM_API_KEY or AUTO_DEPLOYER_GEMINI_API_KEY: LLM API key
    - AUTO_DEPLOYER_LLM_PROXY: HTTP proxy for LLM requests
    - AUTO_DEPLOYER_SSH_HOST: Default SSH host
    - AUTO_DEPLOYER_SSH_PORT: Default SSH port
    - AUTO_DEPLOYER_SSH_USERNAME: Default SSH username
    - AUTO_DEPLOYER_SSH_PASSWORD: Default SSH password
    - AUTO_DEPLOYER_SSH_KEY_PATH: Path to SSH private key
    """

    candidate_paths = []
    if path:
        candidate_paths.append(Path(path))
    candidate_paths.append(_DEFAULT_CONFIG_PATH)

    for candidate in candidate_paths:
        if candidate.is_file():
            with candidate.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            config = AppConfig.from_dict(data)
            
            # Load LLM settings from environment variables
            if not config.llm.api_key:
                provider_key = (
                    f"AUTO_DEPLOYER_{config.llm.provider.upper().replace('-', '_')}_API_KEY"
                )
                config.llm.api_key = os.getenv(provider_key) or os.getenv(
                    "AUTO_DEPLOYER_LLM_API_KEY"
                )
            
            # Load proxy from environment variable
            env_proxy = os.getenv("AUTO_DEPLOYER_LLM_PROXY")
            if env_proxy:
                config.llm.proxy = env_proxy
            
            # Load SSH settings from environment variables
            env_host = os.getenv("AUTO_DEPLOYER_SSH_HOST")
            if env_host:
                config.deployment.default_host = env_host
            
            env_port = os.getenv("AUTO_DEPLOYER_SSH_PORT")
            if env_port:
                config.deployment.default_port = int(env_port)
            
            env_username = os.getenv("AUTO_DEPLOYER_SSH_USERNAME")
            if env_username:
                config.deployment.default_username = env_username
            
            env_password = os.getenv("AUTO_DEPLOYER_SSH_PASSWORD")
            if env_password:
                config.deployment.default_password = env_password
                config.deployment.default_auth_method = "password"
            
            env_key_path = os.getenv("AUTO_DEPLOYER_SSH_KEY_PATH")
            if env_key_path:
                config.deployment.default_key_path = env_key_path
                config.deployment.default_auth_method = "key"
            
            # Apply provider defaults for missing model/endpoint
            # 如果用户未指定 model 或 endpoint，使用提供商默认值
            provider_key = config.llm.provider.lower()
            if provider_key in PROVIDER_DEFAULTS:
                defaults = PROVIDER_DEFAULTS[provider_key]
                
                # 填充 model（如果未指定或为默认值）
                if not config.llm.model or config.llm.model == "planning-v0":
                    if defaults["model"]:
                        config.llm.model = defaults["model"]
                
                # 填充 endpoint（如果未指定）
                if not config.llm.endpoint:
                    config.llm.endpoint = defaults["endpoint"]
            
            return config

    raise FileNotFoundError(
        f"Could not find configuration file. Looked in: {', '.join(str(p) for p in candidate_paths)}"
    )
