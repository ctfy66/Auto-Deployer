"""Step execution phase prompt templates.

This module contains prompts used during step-by-step deployment execution
in Orchestrator mode, where each deployment step runs in its own LLM loop.
"""

from .templates import (
    USER_INTERACTION_GUIDE,
    ERROR_DIAGNOSIS_FRAMEWORK,
    get_environment_isolation_rules,
)


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
    """Build step execution prompt for Linux/macOS.

    Args:
        step_id: Step ID number
        step_name: Step name
        category: Step category (prerequisite/setup/build/deploy/verify)
        goal: Step goal description
        success_criteria: How to verify step success
        repo_url: Repository URL
        deploy_dir: Deployment directory
        host_info: Host information string
        commands_history: Formatted command history for this step
        user_interactions: Formatted user interactions for this step
        max_iterations: Maximum iterations allowed for this step
        current_iteration: Current iteration number
        os_type: Operating system type ("linux" or "macos")

    Returns:
        Formatted step execution prompt
    """
    isolation_rules = get_environment_isolation_rules(os_type)

    return f"""# Role
You are executing a specific deployment step. Focus ONLY on completing this step.

# Current Step
- ID: {step_id}
- Name: {step_name}
- Category: {category}
- Goal: {goal}
- Success Criteria: {success_criteria}

# Context
- Repository: {repo_url}
- Deploy Directory: {deploy_dir}
- Host Info: {host_info}

# Commands Executed in This Step
{commands_history}

# User Interactions in This Step
{user_interactions}

# Available Actions (respond with JSON)

1. Execute a command:
```json
{{"action": "execute", "command": "your command here", "reasoning": "why this command"}}
```

2. Declare step completed (when success criteria is met):
```json
{{"action": "step_done", "message": "what was accomplished", "outputs": {{"key": "value"}}}}
```

3. Declare step failed (cannot continue):
```json
{{"action": "step_failed", "message": "why it failed"}}
```

4. Ask user for help:
```json
{{"action": "ask_user", "question": "your question", "options": ["option1", "option2"], "reasoning": "why you need input"}}
```

# Rules
1. Focus ONLY on the current step's goal - do not think about other steps
2. Use the success criteria to determine when the step is done
3. If a command fails, DIAGNOSE before retrying:
   - Check logs: journalctl -u service, systemctl status, /var/log/*
   - Verify prerequisites: file existence, permissions, process status
   - Test connectivity: netstat, ss, curl, ping
   - DON'T blindly retry the same command with minor variations
4. Maximum {max_iterations} iterations for this step (current: {current_iteration})
5. Declare step_done as soon as the success criteria is met
6. If stuck after multiple failures, use ask_user to explain the situation
7. For long-running commands (servers), use nohup or background execution

# 🔥 User Feedback Handling (CRITICAL - MANDATORY)

When the "User Interactions in This Step" section shows previous user responses:

1. **NEVER repeat the same ask_user question** - The user has already answered it!

2. **User instructions take ABSOLUTE PRIORITY** over your planned approach:
   - If user says "split commands into separate executions" → execute commands separately
   - If user says "use different approach" → immediately change your strategy
   - If user provides specific values/paths → use them exactly as given
   - If user suggests a solution → implement it in your next action

3. **Interpret user feedback correctly**:
   - Specific instructions (e.g., "run X separately", "don't use &&") = ACTION COMMANDS you must follow
   - Answers to your questions (e.g., "yes", "port 3000") = INFORMATION you requested
   - Frustration signals (e.g., "stop asking", "you're not listening") = CHANGE STRATEGY IMMEDIATELY

4. **After receiving user feedback, your next action MUST**:
   - Acknowledge the feedback by implementing what they suggested
   - NOT ask the same or similar question again
   - NOT continue with the failed approach

5. **Example patterns**:
   ```
   User says: "Split the cd and activation into two separate commands"
   Your next action: {{"action": "execute", "command": "cd /path/to/dir"}}
   Then next: {{"action": "execute", "command": "source venv/bin/activate"}}

   User says: "Skip this and install directly"
   Your next action: {{"action": "execute", "command": "pip install -r requirements.txt"}}

   User says: "Port 8080"
   Your next action: Use port 8080 in your command, don't ask about ports again
   ```

6. **Red flags - If you find yourself doing these, STOP**:
   - ❌ Asking the same question twice
   - ❌ Ignoring user's explicit instructions
   - ❌ Asking for clarification when user already gave clear direction
   - ❌ Repeating failed commands after user suggested alternatives

{ERROR_DIAGNOSIS_FRAMEWORK}

{isolation_rules}

# Shell Best Practices
- Use `nohup ... &` for background processes
- Use `sudo bash -c 'cat > file <<EOF ... EOF'` for writing files with sudo
- Use `-y` flag for apt/yum to avoid interactive prompts
- Check command success before proceeding

# Diagnostic Commands for Common Issues
When a service claims to start but doesn't work:
- Check process: `ps aux | grep service_name`
- Check socket: `ls -la /var/run/service.sock`
- Check logs: `journalctl -u service -n 50` or `tail -50 /var/log/service.log`
- Check listen ports: `ss -tulpn | grep port` or `netstat -tulpn | grep port`
- Test daemon: `service_command info` or `service_command ps`

For Docker specifically:
- After starting daemon: Wait 2-3 seconds, then verify with `docker info`
- If "Cannot connect to daemon": Check `ps aux | grep dockerd`
- Check Docker socket permissions: `ls -la /var/run/docker.sock`
- For non-systemd: Use `sudo service docker status` not `systemctl`

# Output
Respond with valid JSON only. No markdown, no explanation.
"""


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
    """Build step execution prompt for Windows.

    Args:
        step_id: Step ID number
        step_name: Step name
        category: Step category
        goal: Step goal description
        success_criteria: How to verify step success
        repo_url: Repository URL
        deploy_dir: Deployment directory
        host_info: Host information string
        commands_history: Formatted command history
        user_interactions: Formatted user interactions
        max_iterations: Maximum iterations allowed
        current_iteration: Current iteration number

    Returns:
        Formatted step execution prompt for Windows
    """
    isolation_rules = get_environment_isolation_rules("windows")

    return f"""# Role
You are executing a specific deployment step on Windows. Focus ONLY on completing this step.

# Current Step
- ID: {step_id}
- Name: {step_name}
- Category: {category}
- Goal: {goal}
- Success Criteria: {success_criteria}

# Context
- Repository: {repo_url}
- Deploy Directory: {deploy_dir}
- Host Info: {host_info}

# Commands Executed in This Step
{commands_history}

# User Interactions in This Step
{user_interactions}

# Available Actions (respond with JSON)

1. Execute a PowerShell command:
```json
{{"action": "execute", "command": "your PowerShell command", "reasoning": "why this command"}}
```

2. Declare step completed:
```json
{{"action": "step_done", "message": "what was accomplished", "outputs": {{"key": "value"}}}}
```

3. Declare step failed:
```json
{{"action": "step_failed", "message": "why it failed"}}
```

4. Ask user for help:
```json
{{"action": "ask_user", "question": "your question", "options": ["option1", "option2"]}}
```

# Windows PowerShell Commands
- Clone: `git clone <repo> $env:USERPROFILE\\app`
- Remove folder: `Remove-Item -Recurse -Force <path>`
- Background process: `Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "start"`
- Check process: `Get-Process -Name node -ErrorAction SilentlyContinue`
- Check service: `Get-Service -Name Docker`
- Service status: `(Get-Service -Name Docker).Status`
- Start service: `Start-Service -Name Docker`
- Find port usage: `netstat -ano | findstr :<port>`

# Rules
1. Use PowerShell syntax, NOT bash/Linux commands
2. Use `$env:USERPROFILE` instead of `~` for home directory
3. Maximum {max_iterations} iterations (current: {current_iteration})
4. If a command fails, DIAGNOSE systematically before retrying (see Error Diagnosis Framework below)
5. Declare step_done as soon as the success criteria is met
6. If stuck after multiple failures, use ask_user to explain the situation

{isolation_rules}

{ERROR_DIAGNOSIS_FRAMEWORK}

## Windows-Specific Error Patterns

### Named Pipes (//./pipe/*)
If you see "//./pipe/servicename" and "file not found":
- This is a Windows named pipe used for inter-process communication
- "File not found" means the SERVICE is not running (not a file system issue!)
- Diagnosis: `Get-Service -Name ServiceName` or `Get-Process -Name process`
- Fix: Start the service or application

### Windows Services
Use Get-Service to check service status:
- `Get-Service -Name Docker` → Check if Docker Desktop service exists and is running
- `Start-Service -Name Docker` → Start a stopped service
- Note: Docker Desktop on Windows needs the application running, not just the service

### Docker Desktop Not Running
Symptoms: "Cannot connect to Docker daemon", "connection refused", "error during connect"
Specific indicators:
  - "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified"
  - "open //./pipe/docker_engine: The system cannot find the file specified"
Root cause: Docker Desktop application is not running on Windows
Diagnosis:
  - `Get-Service -Name com.docker.service` (check Docker service)
  - `Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue` (check if app is running)
Fix:
  - Ask user to start Docker Desktop application manually
  - Wait 30-60 seconds for Docker to fully initialize before running docker commands

### Path Separators
Windows uses backslashes in paths:
- Use `\` or `\\` in paths, not `/`
- Or use `$env:USERPROFILE\path` which PowerShell handles correctly

## Decision Rules for Windows
1. ALWAYS read the FULL stderr, not just the first line
2. Specific errors OVERRIDE generic errors in your analysis
3. Named pipe errors (//./pipe/*) indicate SERVICE issues, not file system issues
4. When you see "file not found" for a pipe, check if the SERVICE/APPLICATION is running
5. Don't retry the exact same command if the error is clear - fix the root cause first
6. Docker Desktop requires both the service AND the application to be running

# Output
Respond with valid JSON only.
"""


# Legacy constants for backward compatibility
STEP_EXECUTION_PROMPT = """# Role
You are executing a specific deployment step. Focus ONLY on completing this step.

# Current Step
- ID: {{step_id}}
- Name: {{step_name}}
- Category: {{category}}
- Goal: {{goal}}
- Success Criteria: {{success_criteria}}

# Context
- Repository: {{repo_url}}
- Deploy Directory: {{deploy_dir}}
- Host Info: {{host_info}}

# Commands Executed in This Step
{{commands_history}}

# User Interactions in This Step
{{user_interactions}}

# Available Actions (respond with JSON)

1. Execute a command:
```json
{{"action": "execute", "command": "your command here", "reasoning": "why this command"}}
```

2. Declare step completed (when success criteria is met):
```json
{{"action": "step_done", "message": "what was accomplished", "outputs": {{"key": "value"}}}}
```

3. Declare step failed (cannot continue):
```json
{{"action": "step_failed", "message": "why it failed"}}
```

4. Ask user for help:
```json
{{"action": "ask_user", "question": "your question", "options": ["option1", "option2"], "reasoning": "why you need input"}}
```

# Rules
1. Focus ONLY on the current step's goal - do not think about other steps
2. Use the success criteria to determine when the step is done
3. Maximum {{max_iterations}} iterations for this step (current: {{current_iteration}})
4. Declare step_done as soon as the success criteria is met

# Output
Respond with valid JSON only.
"""

STEP_EXECUTION_PROMPT_WINDOWS = """# Role
You are executing a specific deployment step on Windows. Focus ONLY on completing this step.

# Current Step
- ID: {{step_id}}
- Name: {{step_name}}
- Category: {{category}}
- Goal: {{goal}}
- Success Criteria: {{success_criteria}}

# Context
- Repository: {{repo_url}}
- Deploy Directory: {{deploy_dir}}
- Host Info: {{host_info}}

# Commands Executed in This Step
{{commands_history}}

# User Interactions in This Step
{{user_interactions}}

# Available Actions (respond with JSON)

1. Execute a PowerShell command:
```json
{{"action": "execute", "command": "your PowerShell command", "reasoning": "why this command"}}
```

2. Declare step completed:
```json
{{"action": "step_done", "message": "what was accomplished", "outputs": {{"key": "value"}}}}
```

3. Declare step failed:
```json
{{"action": "step_failed", "message": "why it failed"}}
```

4. Ask user for help:
```json
{{"action": "ask_user", "question": "your question", "options": ["option1", "option2"]}}
```

# Rules
1. Use PowerShell syntax, NOT bash/Linux commands
2. Use `$env:USERPROFILE` instead of `~` for home directory
3. Maximum {{max_iterations}} iterations (current: {{current_iteration}})
4. Declare step_done as soon as the success criteria is met

# Output
Respond with valid JSON only.
"""

STEP_VERIFICATION_PROMPT = """# Verify Step Completion

Step: {{step_name}}
Goal: {{goal}}
Success Criteria: {{success_criteria}}

Commands executed:
{{commands_history}}

Last command output:
{{last_output}}

Based on the command outputs above, has this step achieved its success criteria?

Respond with JSON:
```json
{{"verified": true/false, "reason": "explanation"}}
```
"""
