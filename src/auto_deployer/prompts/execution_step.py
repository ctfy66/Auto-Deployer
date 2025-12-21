"""Simplified step execution phase prompt templates.

This module contains streamlined prompts for deployment step execution,
optimized for clarity and efficiency while maintaining functionality.
"""

def get_simplified_error_guide() -> str:
    """Get comprehensive error diagnosis guide with timeout strategies."""
    return """
# 🔍 Error Diagnosis

When commands fail:
1. **Identify root cause** - Look for specific error messages, not generic ones
2. **Common patterns**:
   - "Cannot connect" + socket/pipe → Service not running
   - "EADDRINUSE" + port → Port conflict
   - "permission denied" → Need sudo/permissions
   - "command not found" → Install missing tool
   - **"IDLE_TIMEOUT"** → Command waiting for input OR no output
   - **"TOTAL_TIMEOUT"** → Command took too long (>600s)
3. **Fix before retry** - Don't repeat the same failed command
4. **Platform specifics**:
   - Linux: Use `systemctl status`, `sudo`
   - Windows: Check services, named pipes (//./pipe/*)

# ⚠️ TIMEOUT ERRORS - CRITICAL GUIDANCE

**If you see IDLE_TIMEOUT or TOTAL_TIMEOUT in stderr:**

This means you used a BLOCKING command (like `docker logs -f`) or didn't wait long enough for a long-running process.

❌ **NEVER do this:**
- Use `docker logs -f` or `--follow` (causes blocking → timeout)
- Use `tail -f` or any following/watching commands
- Repeatedly check logs without waiting between checks
- Expect instant results from build/install operations

✅ **ALWAYS do this - Progressive Waiting Strategy:**

**For Docker containers doing builds/installs:**
```
1. Start container: docker compose up -d
2. WAIT 60-90 seconds: sleep 60 (or Start-Sleep -Seconds 60)
3. Check briefly: docker logs container_name --tail 20
4. If still building, WAIT 120-180 seconds: sleep 120
5. Check again: docker logs container_name --tail 30
6. If still building, WAIT 300 seconds (5 min): sleep 300
7. Check final status: docker logs container_name --tail 50
```

**For direct npm/pnpm/pip installs (background):**
```
Windows:
1. Start: Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "install"
2. WAIT 60s: Start-Sleep -Seconds 60
3. Check: Get-Process npm

Linux:
1. Start: nohup npm install > install.log 2>&1 &
2. WAIT 60s: sleep 60
3. Check: tail -20 install.log
```

**Key Rules:**
- **WAIT FIRST, CHECK LATER** - Don't spam log checks
- Start with 60-90s wait for first check
- Gradually increase wait time: 60s → 120s → 180s → 300s
- Use `--tail 20` for logs (avoid huge output)
- Maximum reasonable wait: 15 minutes for complex builds

# 🔨 BUILD/INSTALL Operations - Special Handling

**For steps involving: npm install, pnpm install, docker build, pip install, cargo build, etc.**

These operations typically take **2-10 minutes**. You MUST use progressive waiting.

**Mandatory Workflow:**

1️⃣ **Start process in background/detached mode**
   - Docker: `docker compose up -d`
   - Windows PowerShell: `Start-Process -NoNewWindow ...`
   - Linux: `nohup command > output.log 2>&1 &`

2️⃣ **Wait minimum 60 seconds before first check**
   ```
   sleep 60  (Linux)
   Start-Sleep -Seconds 60  (Windows)
   ```

3️⃣ **Check status briefly (not continuously)**
   ```
   docker logs container_name --tail 20
   ```

4️⃣ **Analyze output, if still in progress:**
   - Look for: "downloaded X/Y", "installed X packages", "Building..."
   - These indicate progress → WAIT MORE

5️⃣ **Wait progressively longer (2-3 minutes)**
   ```
   sleep 120
   ```

6️⃣ **Check again**
   ```
   docker logs container_name --tail 30 --since 2m
   ```

7️⃣ **If still not done, wait 5 minutes**
   ```
   sleep 300
   ```

8️⃣ **Final check**
   - If completed: Verify and declare step_done
   - If still building but showing progress: Wait another 5 min
   - If errors or no progress for 15 min: Diagnose and fix

**CORRECT PATTERN Example:**
```json
{"action": "execute", "command": "docker compose up -d"}
{"action": "execute", "command": "Start-Sleep -Seconds 90"}
{"action": "execute", "command": "docker logs buildingai-nodejs --tail 20"}
{"action": "execute", "command": "Start-Sleep -Seconds 180"}
{"action": "execute", "command": "docker logs buildingai-nodejs --tail 30"}
{"action": "execute", "command": "Start-Sleep -Seconds 300"}
{"action": "execute", "command": "docker logs buildingai-nodejs --tail 50"}
```

**WRONG PATTERN (causes timeouts and wastes iterations):**
```json
{"action": "execute", "command": "docker logs -f container"}  ❌ BLOCKS! TIMEOUT!
{"action": "execute", "command": "docker logs container --tail 20"}
{"action": "execute", "command": "docker logs container --tail 20"}  ❌ No wait!
{"action": "execute", "command": "docker logs container --tail 20"}  ❌ Spam!
{"action": "execute", "command": "docker logs container --tail 20"}  ❌ Spam!
```

**Remember:**
- Build processes need TIME, not constant monitoring
- Patience is essential for successful deployment
- Each log check should be preceded by an appropriate wait
- If you see progress indicators, keep waiting
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
    estimated_commands: list | None = None,
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
        estimated_commands: Suggested commands from planning phase

    Returns:
        Formatted step execution prompt
    """
    shell_type = "PowerShell" if os_type.lower() == "windows" else "Bash"
    
    # Build suggested commands section if available
    suggested_cmds_section = ""
    if estimated_commands:
        suggested_cmds_section = "\n## Suggested Commands (from Planning)\n"
        suggested_cmds_section += "The planner suggested these commands for reference:\n"
        for i, cmd in enumerate(estimated_commands, 1):
            suggested_cmds_section += f"{i}. `{cmd}`\n"
        suggested_cmds_section += "\nNote: These are suggestions. Adapt based on actual conditions.\n"

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
{suggested_cmds_section}
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
  "outputs": {{
    "summary": "One sentence describing what was done",
    "key_info": {{"port": 4090}}  // Only if relevant info to pass forward
  }}
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
    estimated_commands: list | None = None,
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
        estimated_commands=estimated_commands,
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
    estimated_commands: list | None = None,
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
        estimated_commands=estimated_commands,
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