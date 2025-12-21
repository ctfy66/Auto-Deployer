"""Prompt templates for step execution.

This module contains prompt templates and schemas for the StepExecutor,
including the required output format for step completion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import StepContext, ExecutionSummary


# JSON Schema for step outputs (用于 LLM 理解输出格式)
STEP_OUTPUT_SCHEMA = """{
  "summary": "string (REQUIRED) - One sentence describing what was accomplished",
  "key_info": {
    "port": 4090,              // If a service was started on a specific port
    "service": "nodejs",       // Service name if applicable
    "deploy_path": "/app",     // Important paths
    "config_file": ".env"      // Key configuration files
  }
}

Note: Only include fields in key_info that are actually relevant to this step.
Empty key_info is acceptable if no critical information needs to be passed forward."""


# 步骤完成指令
STEP_DONE_INSTRUCTION = """
When the step goal is achieved and success criteria are met, you MUST declare completion with:

```json
{
  "action": "step_done",
  "reasoning": "Explanation of why the step is complete",
  "outputs": {
    "summary": "REQUIRED: One sentence describing what was accomplished",
    "key_info": {
      // Only include information that subsequent steps need
      // Examples: {"port": 4090}, {"service": "nodejs", "pid": 12345}, {"config_file": ".env"}
    }
  }
}
```

**IMPORTANT**: 
- The `outputs.summary` field is REQUIRED
- Include `key_info` only if there's critical information to pass forward (e.g., port numbers, service names)
- Empty `key_info` is acceptable: `"key_info": {}`
- Do NOT skip the outputs object when declaring step_done
"""


def _get_error_diagnosis_guide(is_windows: bool = False) -> str:
    """获取错误诊断和处理指南
    
    Args:
        is_windows: 是否是 Windows 环境
        
    Returns:
        错误诊断指南文本
    """
    platform_specific = ""
    if is_windows:
        platform_specific = """
**Windows-Specific Diagnostics:**
- Docker Desktop: Check `Get-Process "Docker Desktop"` to verify it's running
- Services: Use `Get-Service <name>` and `Start-Service <name>`
- Paths: Use `Test-Path` before file operations, escape backslashes properly
- Background processes: Use `Start-Process -NoNewWindow -FilePath "program" -ArgumentList "args"`
- Ports: Use `Get-NetTCPConnection -LocalPort <port>` to check port usage
"""
    else:
        platform_specific = """
**Linux-Specific Diagnostics:**
- Permissions: Use `sudo`, `chmod`, `chown` for permission issues
- Services: Use `systemctl status/start/restart <service>` or `service <service> status`
- Processes: Use `ps aux | grep <name>` or `pgrep <name>`
- Ports: Use `lsof -i :<port>` or `netstat -tuln | grep <port>`
- Background processes: Use `nohup command &` or `command > /dev/null 2>&1 &`
"""
    
    return f"""
---

# Error Diagnosis & Recovery Guide

## Common Error Patterns

When a command fails, identify the error type by matching these patterns:

**2. File System Errors:**
- `No such file or directory` / `PathNotFound` → File/dir doesn't exist, check with Test-Path (Win) or ls (Linux)
- `Permission denied` / `Access denied` → Insufficient permissions, use sudo (Linux) or check file ownership
- `file exists` / `already exists` → Resource conflict, remove old files or use force flag

**3. Service Connection Errors:**
- `Cannot connect` + `socket/pipe` → Service not running, start the service first
- `Connection refused` → Service not listening yet, wait and retry
- `The system cannot find the file specified` + `pipe` → Docker Desktop not running (Windows)

**4. Port Conflicts:**
- `EADDRINUSE` / `address already in use` → Port occupied, find process and kill it or use different port
- Check occupied ports before starting services

**5. Docker Errors:**
- `daemon not running` / `cannot connect to docker` → Start Docker Desktop/daemon first
- `image not found` → Pull image first or check image name
- `mount source path` errors → Check path exists, permissions, or remove old volumes
- `Container ... already exists` → Remove old container with `docker rm -f <container>`

**6. Dependency/Package Errors:**
- `MODULE_NOT_FOUND` / `Cannot find module` → Run npm install or install missing dependency
- `command not found` → Tool not installed, install it first
- `No package ... found` → Wrong package name or repository

**7. Timeout Errors:**
- `IDLE_TIMEOUT: No output for 60 seconds` → Two possible causes:
  1. Command waiting for input (interactive prompts) - use non-interactive alternatives (e.g., `-y` flags)
  2. Long-running operation with no output - use progressive sleep checks (see Progressive Timeout Strategy below)
- `TOTAL_TIMEOUT: Command exceeded 600 seconds` → Command took too long
  - Solution: Use progressive sleep checks with background execution instead of blocking commands (see Progressive Timeout Strategy below)

**8. Build/Compilation Errors:**
- Check logs for specific error messages
- Common: missing dependencies, syntax errors, environment variables not set

{platform_specific}

## Systematic Diagnosis Steps

When a command fails, follow these steps:

1. **Read Full Error Message**
   - Check both stderr AND stdout (sometimes errors are in stdout)
   - Look for specific error codes or messages, not just generic "failed"

2. **Identify Error Type**
   - Match error message against patterns above
   - Determine if it's: filesystem, service, network, permission, or timeout issue

3. **Check Prerequisites**
   - Service running? (`docker ps`, `Get-Service`, `systemctl status`)
   - File exists? (`Test-Path`, `ls`, `[ -f file ]`)
   - Permissions OK? (`ls -la`, `Get-Acl`)
   - Port available? (Use port check commands above)

4. **Collect Context** (if needed)
   - Process list: `Get-Process` / `ps aux`
   - Disk space: `Get-PSDrive` / `df -h`
   - Logs: `docker logs`, service logs, application logs

5. **Apply Fix**
   - Use the appropriate fix for the identified error type
   - Examples:
     - File missing → Create it or install dependencies
     - Service down → Start service and wait for ready
     - Permission issue → Add sudo or fix permissions
     - Port conflict → Change port or kill blocking process

6. **Verify Fix**
   - Re-check the condition that failed
   - Don't immediately retry the same command without verification

## Progressive Timeout Strategy

For long-running processes (builds, installations, service startup):

**DO NOT use `-f`, `--follow`, or blocking commands** - they cause IDLE_TIMEOUT

**Instead, use progressive waiting with status checks:**

```
Step 1: Start process in background
- Windows: Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "run start"
- Linux: nohup npm run start > app.log 2>&1 &
- Docker: docker compose up -d (already detached)

Step 2: Wait 30-60 seconds, then check status
- Command: sleep 30  (or Start-Sleep -Seconds 30 on Windows)
- Check: docker ps, Get-Process, curl -I http://localhost:port

Step 3: If still starting, wait 2-3 minutes, check again
- Command: sleep 120
- Check: docker logs container --tail 50 --since 2m
- Check: service health endpoint

Step 4: If still starting, wait 5 minutes, check again
- Command: sleep 300
- Check: More comprehensive status check

Step 5: If still not ready after 15 minutes total → likely failed
- Check logs for errors
- Consider declaring step_failed if no progress
```

**Key Points:**
- Start with SHORT waits (30-60s), gradually increase
- Check status after EACH wait, don't just wait blindly
- Use `--tail 50 --since 2m` for Docker logs to avoid huge output
- Maximum reasonable wait: 15 minutes for complex builds

## When to Give Up (Declare step_failed)

**You SHOULD declare step_failed when:**

1. **Repeated Failures:** Same command failed 3+ times with same error
2. **Fundamental Issues:**
   - Repository doesn't exist (verified with multiple attempts)
   - Required tool not installed and cannot be installed automatically
   - Docker/service cannot start due to system limitations
3. **User Input Required:**
   - Configuration needs manual decision (which port, which option)
   - Credentials/API keys needed
   - → Use `ask_user` action instead of step_failed
4. **Resource Exhausted:**
   - Exceeded 15 minutes waiting for service with no signs of progress
   - Approaching iteration limit (e.g., used 25/30 iterations) with no solution in sight
5. **Unrecoverable Errors:**
   - Filesystem corruption
   - Incompatible system architecture
   - Critical dependency conflict that requires manual intervention

**You should NOT give up when:**

1. **First Failure:** Always diagnose and attempt fix before giving up
2. **Service Starting:** If logs show progress, continue progressive waiting
3. **Fixable Issues:**
   - Permission errors → try sudo
   - Port conflicts → suggest different port or kill process
   - Missing files → install dependencies
   - Directory exists → remove and reclone
4. **Early in Iteration Budget:** If only used 5/30 iterations, keep trying

**Golden Rule:** Before declaring step_failed, ask yourself:
- "Have I identified the ROOT CAUSE of the error?"
- "Have I tried the appropriate fix for this error type?"
- "Is there anything else I can reasonably try?"

If YES to all three → declare step_failed with clear reasoning
If NO to any → continue diagnosis and fixing

---
"""


def build_step_system_prompt(
    ctx: "StepContext",
    summary: "ExecutionSummary",
    is_windows: bool = False,
) -> str:
    """构建步骤执行的系统提示
    
    Args:
        ctx: 步骤上下文
        summary: 全局执行摘要
        is_windows: 是否是 Windows 环境
        
    Returns:
        完整的系统提示文本
    """
    # 获取摘要上下文
    summary_context = summary.to_prompt_context()
    
    # 平台信息
    if is_windows:
        platform_info = """
## Platform
- OS: Windows
- Shell: PowerShell
- Use PowerShell syntax for all commands
- Use semicolon (;) to chain commands, not &&
- Use `$env:VAR` for environment variables, not $VAR
"""
    else:
        platform_info = """
## Platform
- OS: Linux/Unix
- Shell: Bash
- Use standard bash syntax for commands
"""
    
    # 前置步骤产出信息
    predecessor_info = ""
    if ctx.predecessor_outputs:
        predecessor_info = "\n## Outputs from Previous Steps\n"
        for step_id, outputs in ctx.predecessor_outputs.items():
            predecessor_info += f"\n### Step {step_id}\n"
            predecessor_info += f"- Summary: {outputs.summary}\n"
            if outputs.key_info:
                predecessor_info += f"- Key Info: {outputs.key_info}\n"
    
    # 建议命令（来自规划阶段）
    suggested_commands = ""
    if ctx.estimated_commands:
        suggested_commands = "\n## Suggested Commands (from Planning Phase)\n"
        suggested_commands += "The planner suggested these commands for reference:\n"
        for i, cmd in enumerate(ctx.estimated_commands, 1):
            suggested_commands += f"{i}. `{cmd}`\n"
        suggested_commands += "\nNote: These are suggestions. Adapt them based on actual environment conditions.\n"
    
    # 错误诊断指南
    error_guide = _get_error_diagnosis_guide(is_windows)
    
    return f"""You are a deployment agent executing a specific deployment step.

{summary_context}
{platform_info}
{predecessor_info}
{suggested_commands}
---

# Current Step

- **Step {ctx.step_id}**: {ctx.step_name}
- **Category**: {ctx.category}
- **Goal**: {ctx.goal}
- **Success Criteria**: {ctx.success_criteria}
- **Iteration**: {ctx.iteration}/{ctx.max_iterations}

{error_guide}

# Instructions

1. Focus ONLY on completing this step's goal
2. Use the deployment state above to understand what's already done
3. Execute commands one at a time to achieve the success criteria
4. Check command outputs carefully before proceeding
5. When done, declare completion with structured outputs

# Monitoring Long-Running Processes

For commands that take several minutes (builds, installations, container startup):

**Use progressive waiting strategy:**
```json
// Start the process
{{"action": "execute", "command": "docker compose up -d"}}

// Wait 60 seconds first
{{"action": "execute", "command": "sleep 60"}}
{{"action": "execute", "command": "docker logs container --tail 50"}}

// If still in progress, wait longer (2-3 minutes)
{{"action": "execute", "command": "sleep 120"}}
{{"action": "execute", "command": "docker logs container --tail 50"}}

// If needed, wait even longer (5+ minutes)
{{"action": "execute", "command": "sleep 300"}}
{{"action": "execute", "command": "docker ps --format '{{{{.Status}}}}'"}}
```

**Tips:**
- Start with short waits (60s), gradually increase if process continues
- Check container health status: `docker ps --format '{{{{.Status}}}}'`
- Avoid `-f` or `--follow` flags (they cause timeouts)
- Use `--tail 50 --since 2m` for recent logs without blocking

---

# Response Format

## To execute a command:
```json
{{
  "action": "execute",
  "command": "your command here",
  "reasoning": "why this command is needed"
}}
```

## To ask the user a question:
```json
{{
  "action": "ask_user",
  "question": "your question",
  "options": ["option1", "option2"],
  "reasoning": "why you need this information"
}}
```

## When step is FAILED (cannot proceed):
```json
{{
  "action": "step_failed",
  "message": "description of the failure",
  "reasoning": "why it cannot be resolved"
}}
```

## When step is COMPLETE:
{STEP_DONE_INSTRUCTION}

---

# Output Schema Reference

{STEP_OUTPUT_SCHEMA}

---

Think step by step. Execute commands to achieve the goal. When success criteria are met, declare step_done with outputs.
"""


def build_step_user_prompt(
    ctx: "StepContext",
    last_command_result: dict | None = None,
    user_response: str | None = None,
) -> str:
    """构建步骤执行的用户消息
    
    Args:
        ctx: 步骤上下文
        last_command_result: 上一条命令的执行结果
        user_response: 用户对问题的回复
        
    Returns:
        用户消息文本
    """
    parts = []
    
    # 命令执行结果
    if last_command_result:
        cmd = last_command_result.get("command", "")
        exit_code = last_command_result.get("exit_code", -1)
        stdout = last_command_result.get("stdout", "")
        stderr = last_command_result.get("stderr", "")
        
        parts.append(f"Command executed: `{cmd}`")
        parts.append(f"Exit code: {exit_code}")
        
        if stdout:
            # 截断过长的输出
            if len(stdout) > 2000:
                stdout = stdout[:1000] + "\n... (truncated) ...\n" + stdout[-500:]
            parts.append(f"STDOUT:\n```\n{stdout}\n```")
        
        if stderr:
            if len(stderr) > 1000:
                stderr = stderr[:500] + "\n... (truncated) ...\n" + stderr[-300:]
            parts.append(f"STDERR:\n```\n{stderr}\n```")
    
    # 用户回复
    if user_response:
        parts.append(f"User response: {user_response}")
    
    # 如果没有任何内容，提示开始执行
    if not parts:
        parts.append("Begin executing this step. What is your first action?")
    
    # 添加迭代提醒
    if ctx.iteration > ctx.max_iterations * 0.7:
        remaining = ctx.max_iterations - ctx.iteration
        parts.append(f"\n⚠️ Warning: Only {remaining} iterations remaining for this step!")
    
    return "\n\n".join(parts)
