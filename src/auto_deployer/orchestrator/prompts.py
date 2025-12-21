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

---

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
