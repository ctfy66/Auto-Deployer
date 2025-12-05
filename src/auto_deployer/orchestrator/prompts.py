"""Prompt templates for step-based execution."""

STEP_EXECUTION_PROMPT = """# Role
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
3. If a command fails, analyze the error and try an alternative approach
4. Maximum {max_iterations} iterations for this step (current: {current_iteration})
5. Declare step_done as soon as the success criteria is met
6. For long-running commands (servers), use nohup or background execution

# Shell Best Practices
- Use `nohup ... &` for background processes
- Use `sudo bash -c 'cat > file <<EOF ... EOF'` for writing files with sudo
- Use `-y` flag for apt/yum to avoid interactive prompts
- Check command success before proceeding

# Output
Respond with valid JSON only. No markdown, no explanation.
"""


STEP_EXECUTION_PROMPT_WINDOWS = """# Role
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

# Rules
1. Use PowerShell syntax, NOT bash/Linux commands
2. Use `$env:USERPROFILE` instead of `~` for home directory
3. Maximum {max_iterations} iterations (current: {current_iteration})

# Output
Respond with valid JSON only.
"""


STEP_VERIFICATION_PROMPT = """# Verify Step Completion

Step: {step_name}
Goal: {goal}
Success Criteria: {success_criteria}

Commands executed:
{commands_history}

Last command output:
{last_output}

Based on the command outputs above, has this step achieved its success criteria?

Respond with JSON:
```json
{{"verified": true/false, "reason": "explanation"}}
```
"""

