"""Simplified step execution phase prompt templates.

This module contains streamlined prompts for deployment step execution,
optimized for clarity and efficiency while maintaining functionality.
"""

def get_simplified_error_guide() -> str:
    """Get concise error diagnosis guide."""
    return """
# 🔍 Error Diagnosis

When commands fail:
1. **Identify root cause** - Look for specific error messages, not generic ones
2. **Common patterns**:
   - "Cannot connect" + socket/pipe → Service not running
   - "EADDRINUSE" + port → Port conflict
   - "permission denied" → Need sudo/permissions
   - "command not found" → Install missing tool
3. **Fix before retry** - Don't repeat the same failed command
4. **Platform specifics**:
   - Linux: Use `systemctl status`, `sudo`
   - Windows: Check services, named pipes (//./pipe/*)
"""


def get_simplified_rules(os_type: str = "linux") -> str:
    """Get platform-specific rules."""
    if os_type.lower() == "windows":
        return """
# Windows Rules
- Use PowerShell syntax
- Chain commands with `;` (cd effect doesn't persist)
- Use `$env:USERPROFILE` instead of `~`
- Example: `Set-Location C:\\path; npm install`
"""
    else:
        return """
# Linux/macOS Rules
- Use bash syntax
- Use `&&` to chain commands
- Use `~` for home directory
- Example: `cd ~/app && npm install`
"""


def build_simplified_step_prompt(
    step_id: int,
    step_name: str,
    goal: str,
    success_criteria: str,
    repo_url: str,
    deploy_dir: str,
    host_info: str,
    commands_history: str,
    user_interactions: str,
    max_iterations: int,
    current_iteration: int,
    os_type: str = "linux",
) -> str:
    """Build simplified step execution prompt.

    Args:
        step_id: Step ID number
        step_name: Step name
        goal: Step goal description
        success_criteria: How to verify step success
        repo_url: Repository URL
        deploy_dir: Deployment directory
        host_info: Host information string
        commands_history: Formatted command history for this step
        user_interactions: Formatted user interactions for this step
        max_iterations: Maximum iterations allowed for this step
        current_iteration: Current iteration number
        os_type: Operating system type ("linux", "windows", "macos")

    Returns:
        Formatted step execution prompt
    """
    shell_type = "PowerShell" if os_type.lower() == "windows" else "Bash"

    return f"""# Step {step_id}: {step_name}

## Goal
{goal}

## Success Criteria
{success_criteria}

## Context
- Repository: {repo_url}
- Deploy Directory: {deploy_dir}
- Host: {host_info}
- Shell: {shell_type}
- Iteration: {current_iteration}/{max_iterations}

## Command History
{commands_history}

## User Feedback
{user_interactions}

{get_simplified_error_guide()}

{get_simplified_rules(os_type)}

## Available Actions
Respond with JSON only:

1. **Execute command**:
{{
  "action": "execute",
  "command": "your {shell_type.lower()} command",
  "reasoning": "why this command helps achieve the goal"
}}

2. **Ask user for help**:
{{
  "action": "ask_user",
  "question": "clear question",
  "options": ["option1", "option2"],
  "reasoning": "why you need user input"
}}

3. **Mark step complete** (when success criteria met):
{{
  "action": "step_done",
  "message": "what was accomplished",
  "outputs": {{"key": "value"}}
}}

4. **Mark step failed** (cannot continue):
{{
  "action": "step_failed",
  "message": "why it failed",
  "reasoning": "root cause and attempts made"
}}

## Key Guidelines
- Focus on THIS STEP ONLY - don't think about other steps
- Use success criteria to know when you're done
- If a command fails, analyze before retrying
- Declare step_done as soon as success criteria is met
- For long processes, use background execution (nohup/Start-Process)

## Environment Isolation
- **Python**: Always use virtual environment (venv)
- **Node.js**: Use local dependencies (npm install, not -g)
- **Docker**: Use when Dockerfile present

Respond with valid JSON only (no markdown).
"""


def build_step_execution_prompt(
    step_id: int,
    step_name: str,
    category: str,
    goal: str,
    success_criteria: str,
    repo_url: str,
    deploy_dir: str,
    host_info: str,
    commands_history: str,
    user_interactions: str,
    max_iterations: int,
    current_iteration: int,
    os_type: str = "linux",
) -> str:
    """Simplified version of build_step_execution_prompt.

    This replaces the complex original with a streamlined version.
    """
    return build_simplified_step_prompt(
        step_id=step_id,
        step_name=step_name,
        goal=goal,
        success_criteria=success_criteria,
        repo_url=repo_url,
        deploy_dir=deploy_dir,
        host_info=host_info,
        commands_history=commands_history,
        user_interactions=user_interactions,
        max_iterations=max_iterations,
        current_iteration=current_iteration,
        os_type=os_type,
    )


def build_step_execution_prompt_windows(
    step_id: int,
    step_name: str,
    category: str,
    goal: str,
    success_criteria: str,
    repo_url: str,
    deploy_dir: str,
    host_info: str,
    commands_history: str,
    user_interactions: str,
    max_iterations: int,
    current_iteration: int,
) -> str:
    """Simplified Windows-specific prompt.

    This replaces the complex original with a streamlined version.
    """
    return build_simplified_step_prompt(
        step_id=step_id,
        step_name=step_name,
        goal=goal,
        success_criteria=success_criteria,
        repo_url=repo_url,
        deploy_dir=deploy_dir,
        host_info=host_info,
        commands_history=commands_history,
        user_interactions=user_interactions,
        max_iterations=max_iterations,
        current_iteration=current_iteration,
        os_type="windows",
    )


# Legacy constants for backward compatibility
STEP_EXECUTION_PROMPT = """# Step Execution
Step: {{step_id}} - {{step_name}}

Goal: {{goal}}
Success Criteria: {{success_criteria}}

Context:
- Repository: {{repo_url}}
- Deploy Directory: {{deploy_dir}}
- Host: {{host_info}}

Commands History:
{{commands_history}}

User Interactions:
{{user_interactions}}

Actions:
1. Execute: {"action": "execute", "command": "...", "reasoning": "..."}
2. Ask User: {"action": "ask_user", "question": "...", "options": [...]}
3. Done: {"action": "step_done", "message": "..."}
4. Failed: {"action": "step_failed", "message": "..."}

Maximum {{max_iterations}} iterations (current: {{current_iteration}})

Respond with JSON only.
"""

STEP_EXECUTION_PROMPT_WINDOWS = STEP_EXECUTION_PROMPT

STEP_VERIFICATION_PROMPT = """# Verify Step Completion

Step: {{step_name}}
Goal: {{goal}}
Success Criteria: {{success_criteria}}

Commands executed:
{{commands_history}}

Last output:
{{last_output}}

Has the step achieved its success criteria?

Respond with JSON:
{"verified": true/false, "reason": "explanation"}
"""


# Additional helper functions for even more streamlined prompts
def build_minimal_step_prompt(
    step_id: int,
    step_name: str,
    goal: str,
    success_criteria: str,
    commands_history: str,
    os_type: str = "linux",
) -> str:
    """Build ultra-minimal prompt for simple steps."""
    return f"""# Step {step_id}: {step_name}

Goal: {goal}
Success: {success_criteria}
OS: {os_type}

History:
{commands_history}

Actions:
- execute: Run a command
- step_done: Goal achieved
- step_failed: Cannot continue

Respond with JSON:
{{
  "action": "execute|step_done|step_failed",
  "command": "command if action is execute",
  "reasoning": "why"
}}
"""