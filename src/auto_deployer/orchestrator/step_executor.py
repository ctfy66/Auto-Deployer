"""Step executor: Executes a single deployment step with LLM guidance."""

from __future__ import annotations

import json
import logging
import platform
import time
from typing import Optional, Union, TYPE_CHECKING

import requests

from .models import (
    StepContext, StepResult, StepAction, ActionType,
    CommandRecord, StepStatus, DeployContext
)
from .prompts import STEP_EXECUTION_PROMPT, STEP_EXECUTION_PROMPT_WINDOWS
from ..llm.output_extractor import CommandOutputExtractor

if TYPE_CHECKING:
    from ..ssh import SSHSession
    from ..local import LocalSession
    from ..interaction import UserInteractionHandler
    from ..config import LLMConfig

logger = logging.getLogger(__name__)


class StepExecutor:
    """
    步骤执行器
    
    在单个步骤的边界内执行 LLM 决策循环，直到：
    - 步骤完成（LLM 声明 step_done）
    - 步骤失败（LLM 声明 step_failed 或超过最大迭代）
    """
    
    def __init__(
        self,
        llm_config: "LLMConfig",
        session: Union["SSHSession", "LocalSession"],
        interaction_handler: "UserInteractionHandler",
        max_iterations_per_step: int = 10,
        is_windows: bool = False,
    ):
        self.llm_config = llm_config
        self.session = session
        self.interaction_handler = interaction_handler
        self.max_iterations = max_iterations_per_step
        self.is_windows = is_windows
        
        # HTTP session for LLM calls
        self.http_session = requests.Session()
        self._setup_proxy()
        
        # LLM endpoint
        self.base_endpoint = llm_config.endpoint or (
            f"https://generativelanguage.googleapis.com/v1beta/models/{llm_config.model}:generateContent"
        )

        # 输出提取器
        self.output_extractor = CommandOutputExtractor(
            max_success_lines=30,
            max_error_lines=50
        )
    
    def _setup_proxy(self) -> None:
        """设置代理"""
        import os
        proxy = self.llm_config.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy:
            self.http_session.proxies = {"http": proxy, "https": proxy}
            logger.debug("StepExecutor using proxy: %s", proxy)
    
    def execute(
        self,
        step_ctx: StepContext,
        deploy_ctx: DeployContext,
    ) -> StepResult:
        """
        执行单个步骤
        
        Args:
            step_ctx: 步骤上下文（包含目标、成功标准等）
            deploy_ctx: 全局部署上下文
            
        Returns:
            StepResult: 步骤执行结果
        """
        step_ctx.status = StepStatus.RUNNING
        step_ctx.max_iterations = self.max_iterations
        
        logger.info(f"   Goal: {step_ctx.goal}")
        logger.info(f"   Success criteria: {step_ctx.success_criteria}")
        
        for iteration in range(1, self.max_iterations + 1):
            step_ctx.iteration = iteration
            logger.debug(f"   Iteration {iteration}/{self.max_iterations}")
            
            # 获取 LLM 决策
            action = self._get_next_action(step_ctx, deploy_ctx)
            
            if action.action_type == ActionType.EXECUTE:
                # 执行命令
                logger.info(f"   🔧 [{iteration}] {action.command}")
                if action.reasoning:
                    logger.debug(f"      Reason: {action.reasoning}")
                
                record = self._execute_command(action.command)
                step_ctx.commands.append(record)
                
                status = "✓" if record.success else "✗"
                logger.info(f"      {status} Exit code: {record.exit_code}")
                
                if record.stdout and len(record.stdout) < 200:
                    logger.debug(f"      stdout: {record.stdout}")
                if record.stderr and not record.success:
                    logger.warning(f"      stderr: {record.stderr[:200]}")
                
            elif action.action_type == ActionType.STEP_DONE:
                # 步骤完成
                logger.info(f"   ✅ Step completed: {action.message}")
                step_ctx.status = StepStatus.SUCCESS
                step_ctx.outputs = action.outputs or {}
                return StepResult.succeeded(outputs=step_ctx.outputs)
                
            elif action.action_type == ActionType.STEP_FAILED:
                # 步骤失败
                logger.error(f"   ❌ Step failed: {action.message}")
                step_ctx.status = StepStatus.FAILED
                step_ctx.error = action.message
                return StepResult.failed(error=action.message or "Unknown error")
                
            elif action.action_type == ActionType.ASK_USER:
                # 询问用户
                logger.info(f"   💬 Asking user: {action.question}")
                response = self._ask_user(action)
                
                if response.get("cancelled"):
                    logger.info("   User cancelled")
                    step_ctx.status = StepStatus.FAILED
                    return StepResult.failed(error="User cancelled")
                
                step_ctx.user_interactions.append({
                    "question": action.question,
                    "response": response.get("value"),
                })
                logger.info(f"   User replied: {response.get('value')}")
        
        # 超过最大迭代
        error_msg = f"Exceeded max iterations ({self.max_iterations}) for this step"
        logger.error(f"   ❌ {error_msg}")
        step_ctx.status = StepStatus.FAILED
        step_ctx.error = error_msg
        return StepResult.failed(error=error_msg)
    
    def _get_next_action(
        self,
        step_ctx: StepContext,
        deploy_ctx: DeployContext,
    ) -> StepAction:
        """调用 LLM 获取下一步动作"""
        
        # 选择 prompt 模板
        template = STEP_EXECUTION_PROMPT_WINDOWS if self.is_windows else STEP_EXECUTION_PROMPT
        
        # 构建 prompt
        prompt = template.format(
            step_id=step_ctx.step_id,
            step_name=step_ctx.step_name,
            category=step_ctx.category,
            goal=step_ctx.goal,
            success_criteria=step_ctx.success_criteria,
            repo_url=deploy_ctx.repo_url,
            deploy_dir=deploy_ctx.deploy_dir,
            host_info=json.dumps(deploy_ctx.host_info, indent=2, ensure_ascii=False),
            commands_history=self._format_commands(step_ctx.commands),
            user_interactions=self._format_interactions(step_ctx.user_interactions),
            max_iterations=self.max_iterations,
            current_iteration=step_ctx.iteration,
        )
        
        # 调用 LLM
        response_text = self._call_llm(prompt)
        
        # 解析响应
        return self._parse_action(response_text)
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API"""
        url = f"{self.base_endpoint}?key={self.llm_config.api_key}"
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.llm_config.temperature,
                "responseMimeType": "application/json",
            },
        }
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.http_session.post(url, json=body, timeout=60)
                
                if response.status_code == 429:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                candidates = data.get("candidates", [])
                for candidate in candidates:
                    parts = candidate.get("content", {}).get("parts", [])
                    for part in parts:
                        if text := part.get("text"):
                            return text
                
                return '{"action": "step_failed", "message": "No LLM response"}'
                
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429 and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                logger.error(f"LLM API call failed: {e}")
                return f'{{"action": "step_failed", "message": "LLM error: {str(e)}"}}'
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                if attempt == max_retries - 1:
                    return f'{{"action": "step_failed", "message": "LLM error: {str(e)}"}}'
        
        return '{"action": "step_failed", "message": "Rate limited after max retries"}'
    
    def _parse_action(self, text: str) -> StepAction:
        """解析 LLM 响应为 StepAction"""
        try:
            data = json.loads(text)
            action_str = data.get("action", "step_failed")
            action_map = {
                "execute": ActionType.EXECUTE,
                "step_done": ActionType.STEP_DONE,
                "step_failed": ActionType.STEP_FAILED,
                "ask_user": ActionType.ASK_USER,
            }
            return StepAction(
                action_type=action_map.get(action_str, ActionType.STEP_FAILED),
                command=data.get("command"),
                reasoning=data.get("reasoning"),
                message=data.get("message"),
                question=data.get("question"),
                options=data.get("options"),
                outputs=data.get("outputs"),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Raw response: {text[:200]}")
            return StepAction(
                action_type=ActionType.STEP_FAILED,
                message=f"Failed to parse LLM response: {text[:100]}"
            )
    
    def _execute_command(self, command: str) -> CommandRecord:
        """执行命令并智能提取输出"""
        try:
            result = self.session.run(command, timeout=120)

            # 使用智能提取器处理输出
            extracted = self.output_extractor.extract(
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                success=result.ok,
                exit_code=result.exit_status,
                command=command
            )

            # 返回包含提取后输出的CommandRecord
            return CommandRecord(
                command=command,
                success=result.ok,
                exit_code=result.exit_status,
                # 使用提取后的输出替代原始截断输出
                stdout=self.output_extractor.format_for_llm(extracted),
                stderr="",  # 错误已整合到stdout的格式化输出中
                timestamp=extracted.summary if hasattr(extracted, 'summary') else ""
            )
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return CommandRecord(
                command=command,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                timestamp=""
            )
    
    def _ask_user(self, action: StepAction) -> dict:
        """询问用户"""
        from ..interaction import InteractionRequest, InputType, QuestionCategory
        
        request = InteractionRequest(
            question=action.question or "",
            options=action.options or [],
            input_type=InputType.CHOICE if action.options else InputType.TEXT,
            category=QuestionCategory.DECISION,
            allow_custom=True,
        )
        response = self.interaction_handler.ask(request)
        return {
            "value": response.value,
            "cancelled": response.cancelled,
        }
    
    def _format_commands(self, commands: list) -> str:
        """格式化命令历史"""
        if not commands:
            return "(no commands executed yet)"
        
        lines = []
        for i, cmd in enumerate(commands[-5:], 1):  # 最近5条
            status = "SUCCESS" if cmd.success else "FAILED"
            lines.append(f"{i}. [{status}] {cmd.command}")
            if cmd.stdout:
                # 截取输出
                stdout_preview = cmd.stdout[:300].replace('\n', '\n   ')
                lines.append(f"   stdout: {stdout_preview}")
            if cmd.stderr and not cmd.success:
                stderr_preview = cmd.stderr[:200].replace('\n', '\n   ')
                lines.append(f"   stderr: {stderr_preview}")
        return "\n".join(lines)
    
    def _format_interactions(self, interactions: list) -> str:
        """格式化用户交互历史"""
        if not interactions:
            return "(no user interactions)"
        
        lines = []
        for i, item in enumerate(interactions[-3:], 1):
            lines.append(f"{i}. Q: {item['question']}")
            lines.append(f"   A: {item['response']}")
        return "\n".join(lines)

