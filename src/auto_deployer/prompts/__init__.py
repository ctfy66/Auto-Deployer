"""Unified prompt management module.

This module provides centralized access to all prompt templates used throughout
the deployment system, including planning, execution, and system prompts.

Usage:
    from auto_deployer.prompts import (
        build_planning_prompt,
        build_step_execution_prompt,
        build_agent_prompt,
    )
"""

# Planning prompts
from .planning import (
    build_planning_prompt,
    build_host_details_local,
    build_host_details_remote,
)

# Step execution prompts (Orchestrator mode)
from .execution_step import (
    build_step_execution_prompt,
    build_step_execution_prompt_windows,
    STEP_EXECUTION_PROMPT,  # Legacy constant for backward compatibility
    STEP_EXECUTION_PROMPT_WINDOWS,  # Legacy constant
    STEP_VERIFICATION_PROMPT,  # Legacy constant
)

# Reusable templates
from .templates import (
    USER_INTERACTION_GUIDE,
    ERROR_DIAGNOSIS_FRAMEWORK,
    ENVIRONMENT_ISOLATION_PYTHON,
    ENVIRONMENT_ISOLATION_NODEJS,
    ENVIRONMENT_ISOLATION_DOCKER,
    ENVIRONMENT_ISOLATION_PYTHON_WINDOWS,
    ENVIRONMENT_ISOLATION_NODEJS_WINDOWS,
    get_environment_isolation_rules,
    get_deployment_strategies,
)

__all__ = [
    # Planning
    "build_planning_prompt",
    "build_host_details_local",
    "build_host_details_remote",
    # Step execution
    "build_step_execution_prompt",
    "build_step_execution_prompt_windows",
    "STEP_EXECUTION_PROMPT",
    "STEP_EXECUTION_PROMPT_WINDOWS",
    "STEP_VERIFICATION_PROMPT",
    # Templates
    "USER_INTERACTION_GUIDE",
    "ERROR_DIAGNOSIS_FRAMEWORK",
    "ENVIRONMENT_ISOLATION_PYTHON",
    "ENVIRONMENT_ISOLATION_NODEJS",
    "ENVIRONMENT_ISOLATION_DOCKER",
    "ENVIRONMENT_ISOLATION_PYTHON_WINDOWS",
    "ENVIRONMENT_ISOLATION_NODEJS_WINDOWS",
    "get_environment_isolation_rules",
    "get_deployment_strategies",
]
