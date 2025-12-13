"""Step executor: Executes a single deployment step with LLM guidance."""

from __future__ import annotations

import json
import logging
import platform
from typing import Optional, Union, TYPE_CHECKING

from .models import (
    StepContext, StepResult, StepAction, ActionType,
    CommandRecord, StepStatus, DeployContext, StepOutputs, ExecutionSummary
)
from .prompts import build_step_system_prompt, build_step_user_prompt
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
        
        # Initialize LLM provider using factory
        from ..llm.base import create_llm_provider
        self.llm_provider = create_llm_provider(llm_config)
        logger.info("StepExecutor using LLM provider: %s (model: %s)", llm_config.provider, llm_config.model)

        # 输出提取器
        self.output_extractor = CommandOutputExtractor(
            max_success_lines=30,
            max_error_lines=50
        )
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
                command = action.command or ""
                logger.info(f"   🔧 [{iteration}] {command}")
                if action.reasoning:
                    logger.info(f"      💭 Reason: {action.reasoning}")
                
                record = self._execute_command(command, action.reasoning)
                step_ctx.commands.append(record)
                
                status = "✓" if record.success else "✗"
                logger.info(f"      {status} Exit code: {record.exit_code}")
                
                if record.stdout and len(record.stdout) < 200:
                    logger.debug(f"      stdout: {record.stdout}")
                if record.stderr and not record.success:
                    logger.warning(f"      stderr: {record.stderr[:200]}")
                
            elif action.action_type == ActionType.STEP_DONE:
                # 步骤完成 - 验证并处理结构化产出
                logger.info(f"   ✅ Step completed: {action.message}")
                step_ctx.status = StepStatus.SUCCESS
                
                # 验证并解析结构化产出
                structured_outputs = self._validate_outputs(action.outputs)
                if structured_outputs:
                    step_ctx.structured_outputs = structured_outputs
                    step_ctx.outputs = structured_outputs.to_dict()
                    logger.info(f"   📦 Outputs: {structured_outputs.summary}")
                else:
                    # 如果没有有效的结构化产出，创建一个基本的
                    step_ctx.outputs = action.outputs or {}
                    logger.warning("   ⚠️ No structured outputs provided")
                
                return StepResult.succeeded(
                    outputs=step_ctx.outputs,
                    structured_outputs=structured_outputs
                )
                
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
        
        # 使用函数式 prompt 构建器（而不是已弃用的常量）
        from ..prompts.execution_step import (
            build_step_execution_prompt,
            build_step_execution_prompt_windows
        )
        
        # 构建 prompt
        if self.is_windows:
            prompt = build_step_execution_prompt_windows(
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
        else:
            prompt = build_step_execution_prompt(
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
                os_type="linux",
            )
        
        # 调用 LLM
        response_text = self._call_llm(prompt)
        
        # 解析响应
        return self._parse_action(response_text)
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM API（通过 provider 抽象层）"""
        try:
            response_text = self.llm_provider.generate_response(
                prompt=prompt,
                response_format="json",
                timeout=60,
                max_retries=3
            )
            
            if not response_text:
                logger.error("No response from LLM provider")
                return '{"action": "step_failed", "message": "No LLM response"}'
            
            return response_text
            
        except Exception as e:
            logger.error(f"LLM provider call failed: {e}")
            return f'{{"action": "step_failed", "message": "LLM error: {str(e)}"}}'
    
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
    
    def _execute_command(self, command: str, reasoning: Optional[str] = None) -> CommandRecord:
        """执行命令并智能提取输出"""
        try:
            result = self.session.run(command, timeout=600, idle_timeout=60)

            # 使用智能提取器处理输出
            extracted = self.output_extractor.extract(
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                success=result.ok,
                exit_code=result.exit_status,
                command=command
            )

            # 格式化为LLM可读的输出
            formatted_output = self.output_extractor.format_for_llm(extracted)

            # 打印到终端 - 显示提取后的输出
            print("\n" + "=" * 60)
            print("📤 LLM将看到的提取后输出:")
            print("-" * 60)
            print(formatted_output)
            print("=" * 60 + "\n")

            # 记录到日志
            logger.info(f"Extracted output for LLM (original: {extracted.full_length} chars, extracted: {extracted.extracted_length} chars):")
            logger.info(f"Summary: {extracted.summary}")
            if extracted.key_info:
                logger.debug(f"Key info: {extracted.key_info[:5]}")  # 只记录前5条

            # 返回包含提取后输出和reasoning的CommandRecord
            # 注意：CommandRecord需要扩展以支持reasoning和extracted_output字段
            record = CommandRecord(
                command=command,
                success=result.ok,
                exit_code=result.exit_status,
                # 使用提取后的输出替代原始截断输出
                stdout=formatted_output,
                stderr="",  # 错误已整合到stdout的格式化输出中
                timestamp=extracted.summary if hasattr(extracted, 'summary') else ""
            )
            
            # 临时存储额外信息（用于日志记录）
            record._reasoning = reasoning  # type: ignore
            record._extracted_output = formatted_output  # type: ignore
            record._original_stdout = result.stdout[:2000] if result.stdout else ""  # type: ignore
            record._original_stderr = result.stderr[:2000] if result.stderr else ""  # type: ignore
            
            return record
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
    
    def _validate_outputs(self, outputs_dict: Optional[dict]) -> Optional[StepOutputs]:
        """验证并解析步骤产出
        
        Args:
            outputs_dict: LLM 返回的 outputs 字典
            
        Returns:
            StepOutputs 对象，如果验证失败则返回 None
        """
        if not outputs_dict:
            logger.warning("No outputs provided in step_done action")
            return None
        
        if not isinstance(outputs_dict, dict):
            logger.warning(f"Outputs is not a dict: {type(outputs_dict)}")
            return None
        
        # 验证必填字段
        summary = outputs_dict.get("summary")
        if not summary or not isinstance(summary, str):
            logger.warning("outputs.summary is required and must be a string")
            # 尝试从其他字段生成摘要
            if outputs_dict.get("message"):
                summary = str(outputs_dict["message"])
            else:
                summary = "Step completed"
        
        try:
            return StepOutputs(
                summary=summary,
                environment_changes=outputs_dict.get("environment_changes", {}),
                new_configurations=outputs_dict.get("new_configurations", {}),
                artifacts=outputs_dict.get("artifacts", []),
                services_started=outputs_dict.get("services_started", []),
                custom_data=outputs_dict.get("custom_data", {}),
                issues_resolved=outputs_dict.get("issues_resolved", []),
            )
        except Exception as e:
            logger.error(f"Failed to create StepOutputs: {e}")
            return None
    
    def _get_next_action_with_summary(
        self,
        step_ctx: StepContext,
        deploy_ctx: DeployContext,
        execution_summary: Optional[ExecutionSummary] = None,
        last_command_result: Optional[dict] = None,
        user_response: Optional[str] = None,
    ) -> StepAction:
        """使用新的 prompt 模板获取 LLM 决策（带执行摘要）
        
        Args:
            step_ctx: 步骤上下文
            deploy_ctx: 部署上下文
            execution_summary: 全局执行摘要
            last_command_result: 上一条命令的结果
            user_response: 用户回复
            
        Returns:
            StepAction 决策
        """
        # 如果有执行摘要，使用新的 prompt 模板
        if execution_summary:
            system_prompt = build_step_system_prompt(
                ctx=step_ctx,
                summary=execution_summary,
                is_windows=self.is_windows,
            )
            user_prompt = build_step_user_prompt(
                ctx=step_ctx,
                last_command_result=last_command_result,
                user_response=user_response,
            )
            
            # 组合 prompt
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
            
            # 调用 LLM
            response_text = self._call_llm(full_prompt)
            return self._parse_action(response_text)
        else:
            # 回退到旧方法
            return self._get_next_action(step_ctx, deploy_ctx)

