"""Step executor: Executes a single deployment step with LLM guidance."""

from __future__ import annotations

import json
import logging
import platform
from datetime import datetime
from typing import Optional, Union, TYPE_CHECKING, Callable

from .models import (
    StepContext, StepResult, StepAction, ActionType,
    CommandRecord, StepStatus, DeployContext, StepOutputs, ExecutionSummary, LoopDetectionResult
)
from .prompts import build_step_system_prompt, build_step_user_prompt

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
        on_command_executed: Optional[Callable[[], None]] = None,
        loop_detection_enabled: bool = True,
    ):
        self.llm_config = llm_config
        self.session = session
        self.interaction_handler = interaction_handler
        self.max_iterations = max_iterations_per_step
        self.is_windows = is_windows
        self.on_command_executed = on_command_executed
        
        # Initialize LLM provider using factory
        from ..llm.base import create_llm_provider
        self.llm_provider = create_llm_provider(llm_config)
        logger.info("StepExecutor using LLM provider: %s (model: %s)", llm_config.provider, llm_config.model)

        # Initialize token manager and history compressor
        from ..llm.token_manager import TokenManager
        from ..llm.history_compressor import HistoryCompressor
        
        self.token_manager = TokenManager(llm_config.provider, llm_config.model)
        self.history_compressor = HistoryCompressor(self.llm_provider)
        
        # Initialize loop detection components
        from .loop_detector import LoopDetector
        from .loop_intervention import LoopInterventionManager
        
        self.loop_detector = LoopDetector(
            enabled=loop_detection_enabled,
            direct_repeat_threshold=3,
            error_loop_threshold=4,
            command_similarity_threshold=0.85,
            output_similarity_threshold=0.80,
        )
        self.loop_intervention_manager = LoopInterventionManager(
            temperature_boost_levels=[0.3, 0.5, 0.7]
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
        
        # Reset loop intervention manager for this step
        self.loop_intervention_manager.reset()
        
        logger.info(f"   Goal: {step_ctx.goal}")
        logger.info(f"   Success criteria: {step_ctx.success_criteria}")
        
        for iteration in range(1, self.max_iterations + 1):
            step_ctx.iteration = iteration
            logger.debug(f"   Iteration {iteration}/{self.max_iterations}")
            
            # === Loop Detection ===
            if len(step_ctx.commands) >= 3:
                detection = self.loop_detector.check(step_ctx.commands)
                
                if detection.is_loop:
                    logger.warning(f"   🔄 Loop detected: {detection.loop_type} (confidence: {detection.confidence:.2%})")
                    for evidence in detection.evidence:
                        logger.warning(f"      • {evidence}")
                    
                    # Decide intervention
                    intervention = self.loop_intervention_manager.decide_intervention(
                        detection, iteration
                    )
                    
                    logger.info(f"   {intervention['message']}")
                    
                    if intervention['action'] == 'boost_temperature':
                        # Boost temperature
                        self.llm_config.temperature = intervention['temperature']
                        logger.info(f"      Temperature: {self.llm_config.temperature}")
                    
                    elif intervention['action'] == 'inject_reflection':
                        # Inject reflection prompt
                        step_ctx.reflection_prompt = intervention['reflection_text']
                        self.llm_config.temperature = intervention['temperature']
                        logger.info(f"      Reflection injected, temperature: {self.llm_config.temperature}")
                    
                    elif intervention['action'] == 'ask_user':
                        # Ask user for intervention
                        self.llm_config.temperature = intervention['temperature']
                        user_decision = self._handle_loop_intervention(detection, step_ctx)
                        
                        if user_decision == 'abort':
                            step_ctx.status = StepStatus.FAILED
                            step_ctx.error = "User aborted due to severe loop"
                            return StepResult.failed(error="User aborted due to severe loop")
                        elif user_decision == 'skip':
                            step_ctx.status = StepStatus.SKIPPED
                            return StepResult.skipped(reason="User skipped due to loop")
                        # Otherwise continue with user guidance
            
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
                
                # 立即保存日志
                if self.on_command_executed:
                    self.on_command_executed()
                
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
                commands_history=self._format_commands(step_ctx),
                user_interactions=self._format_interactions(step_ctx.user_interactions),
                max_iterations=self.max_iterations,
                current_iteration=step_ctx.iteration,
                estimated_commands=step_ctx.estimated_commands,
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
                commands_history=self._format_commands(step_ctx),
                user_interactions=self._format_interactions(step_ctx.user_interactions),
                max_iterations=self.max_iterations,
                current_iteration=step_ctx.iteration,
                os_type="linux",
                estimated_commands=step_ctx.estimated_commands,
            )
        
        # 检查token使用量，如果达到阈值则触发压缩
        if self.token_manager.should_compress(prompt, threshold=0.5):
            logger.info(f"   🔄 Token threshold reached at iteration {step_ctx.iteration}, compressing command history...")
            step_ctx = self._compress_step_history(step_ctx)
            
            # 重新构建prompt
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
                    commands_history=self._format_commands(step_ctx),
                    user_interactions=self._format_interactions(step_ctx.user_interactions),
                    max_iterations=self.max_iterations,
                    current_iteration=step_ctx.iteration,
                    estimated_commands=step_ctx.estimated_commands,
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
                    commands_history=self._format_commands(step_ctx),
                    user_interactions=self._format_interactions(step_ctx.user_interactions),
                    max_iterations=self.max_iterations,
                    current_iteration=step_ctx.iteration,
                    os_type="linux",
                    estimated_commands=step_ctx.estimated_commands,
                )
        
        # 插入反思prompt（如果存在）
        if step_ctx.reflection_prompt:
            prompt = step_ctx.reflection_prompt + "\n\n" + prompt
            logger.debug("   Reflection prompt injected into LLM call")
            # 清除反思prompt，避免重复注入
            step_ctx.reflection_prompt = None
        
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
    
    def _get_smart_timeout(self, command: str) -> tuple[int, int]:
        """根据命令内容返回合理的超时值
        
        Args:
            command: 要执行的命令
            
        Returns:
            (timeout, idle_timeout) 元组
        """
        import re
        
        # 默认值
        timeout = 600        # 10分钟
        idle_timeout = 60    # 1分钟
        
        # 检测sleep/wait命令，延长总超时
        sleep_patterns = [
            r'sleep\s+(\d+)',                    # Linux: sleep 300
            r'Start-Sleep\s+-Seconds\s+(\d+)',   # PowerShell: Start-Sleep -Seconds 300
            r'timeout\s+/t\s+(\d+)',             # Windows CMD: timeout /t 300
        ]
        for pattern in sleep_patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if match:
                sleep_duration = int(match.group(1))
                # 总超时 = sleep时间 + 120秒余量
                timeout = max(timeout, sleep_duration + 120)
                break
        
        # 检测长时间运行的构建/安装命令
        long_running_commands = [
            'npm install',
            'npm ci',
            'pnpm install',
            'pnpm i',
            'yarn install',
            'pip install',
            'docker build',
            'docker compose up',
            'docker-compose up',
            'cargo build',
            'mvn install',
            'gradle build',
        ]
        
        command_lower = command.lower()
        if any(cmd in command_lower for cmd in long_running_commands):
            timeout = 1800       # 30分钟
            idle_timeout = 180   # 3分钟
        
        # 检测monitoring命令（带-f或--follow标志）
        if re.search(r'-f\b|--follow\b', command):
            idle_timeout = 300   # 5分钟
        
        return timeout, idle_timeout
    
    def _execute_command(self, command: str, reasoning: Optional[str] = None) -> CommandRecord:
        """执行命令并保存完整输出"""
        try:
            # 智能检测超时参数
            timeout, idle_timeout = self._get_smart_timeout(command)
            
            # 记录使用的超时值（调试用）
            logger.debug(f"Executing command with timeout={timeout}s, idle_timeout={idle_timeout}s")
            
            result = self.session.run(command, timeout=timeout, idle_timeout=idle_timeout)

            # 直接使用完整输出，不再提取
            record = CommandRecord(
                command=command,
                success=result.ok,
                exit_code=result.exit_status,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                timestamp=datetime.now().isoformat()
            )
            
            # 日志输出（可选择性截断显示）
            logger.info(f"Command executed: {command}")
            logger.info(f"Exit code: {result.exit_status}")
            
            # 只在终端显示简短摘要
            if result.stdout and len(result.stdout) < 500:
                logger.debug(f"stdout preview: {result.stdout[:500]}")
            elif result.stdout:
                logger.debug(f"stdout: {len(result.stdout)} characters")
            
            if result.stderr:
                if not result.ok:
                    # 失败时显示错误
                    logger.warning(f"stderr: {result.stderr[:500]}")
                else:
                    logger.debug(f"stderr: {len(result.stderr)} characters")
            
            return record
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return CommandRecord(
                command=command,
                success=False,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                timestamp=datetime.now().isoformat()
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
    
    def _handle_loop_intervention(self, detection: LoopDetectionResult, step_ctx: StepContext) -> str:
        """处理严重循环，询问用户如何处理
        
        Args:
            detection: 循环检测结果
            step_ctx: 步骤上下文
            
        Returns:
            str: 用户决定 ("continue" | "skip" | "abort" | "guidance")
        """
        from ..interaction import InteractionRequest, InputType, QuestionCategory
        
        evidence_text = "\n".join(f"  • {e}" for e in detection.evidence)
        
        question = f"""
Agent appears stuck in a loop ({detection.loop_type}, confidence: {detection.confidence:.1%}):

{evidence_text}

This is the {self.loop_intervention_manager.loop_count}th time a loop has been detected.

What would you like to do?
"""
        
        request = InteractionRequest(
            question=question,
            options=[
                "Continue (let agent try with higher temperature)",
                "Skip this step",
                "Abort deployment",
                "Provide guidance (custom input)"
            ],
            input_type=InputType.CHOICE,
            category=QuestionCategory.ERROR_RECOVERY,
            allow_custom=True,
        )
        
        response = self.interaction_handler.ask(request)
        
        if response.cancelled:
            return "abort"
        
        choice = response.value.lower()
        
        if "continue" in choice:
            return "continue"
        elif "skip" in choice:
            return "skip"
        elif "abort" in choice:
            return "abort"
        elif "guidance" in choice or "custom" in choice:
            # Ask for custom guidance
            guidance_request = InteractionRequest(
                question="Please provide guidance for the agent:",
                options=[],
                input_type=InputType.TEXT,
                category=QuestionCategory.INFORMATION,
            )
            guidance_response = self.interaction_handler.ask(guidance_request)
            
            if not guidance_response.cancelled and guidance_response.value:
                # Inject user guidance as reflection
                step_ctx.reflection_prompt = f"""
USER GUIDANCE:
{guidance_response.value}

Please follow the user's guidance carefully.
"""
                logger.info(f"   User guidance injected: {guidance_response.value[:100]}...")
            
            return "continue"
        else:
            return "continue"
    
    
    def _compress_step_history(self, step_ctx: StepContext) -> StepContext:
        """压缩当前步骤的命令历史
        
        保留最近30%的命令，压缩较远的70%
        """
        from datetime import datetime
        from .models import CompressionEvent
        
        total_commands = len(step_ctx.commands)
        if total_commands < 10:
            # 命令太少不压缩
            logger.debug(f"   Skipping compression: only {total_commands} commands")
            return step_ctx
        
        # 保留最近30%（至少保留3条）
        keep_count = max(3, int(total_commands * 0.3))
        recent_commands = step_ctx.commands[-keep_count:]
        old_commands = step_ctx.commands[:-keep_count]
        
        logger.debug(f"   Compressing {len(old_commands)} commands, keeping {len(recent_commands)} recent")
        
        # 计算压缩前的token数量
        token_count_before = None
        try:
            # 构建完整的命令历史文本用于token计数
            full_history = self._format_commands(step_ctx)
            token_count_before = self.token_manager.count_tokens(full_history)
        except Exception as e:
            logger.debug(f"   Failed to count tokens before compression: {e}")
        
        # 调用LLM压缩
        try:
            compressed_text = self.history_compressor.compress(
                commands=old_commands,
                step_name=step_ctx.step_name,
                step_goal=step_ctx.goal,
            )
            
            # 更新上下文
            step_ctx.compressed_history = compressed_text
            step_ctx.commands = recent_commands
            
            # 计算压缩后的token数量
            token_count_after = None
            compression_ratio = 0.0
            try:
                new_history = self._format_commands(step_ctx)
                token_count_after = self.token_manager.count_tokens(new_history)
                
                if token_count_before and token_count_after:
                    compression_ratio = ((token_count_before - token_count_after) / token_count_before) * 100
            except Exception as e:
                logger.debug(f"   Failed to count tokens after compression: {e}")
            
            # 获取token限制用于触发原因
            token_limit = self.token_manager.get_limit()
            trigger_reason = f"Token threshold 50% reached ({token_count_before}/{token_limit} tokens)" if token_count_before else "Token threshold reached"
            
            # 创建压缩事件记录
            compression_event = CompressionEvent(
                iteration=step_ctx.iteration,
                commands_before=total_commands,
                commands_compressed=len(old_commands),
                commands_kept=len(recent_commands),
                compressed_text_length=len(compressed_text),
                token_count_before=token_count_before,
                token_count_after=token_count_after,
                compression_ratio=compression_ratio,
                timestamp=datetime.now().isoformat(),
                trigger_reason=trigger_reason,
            )
            
            # 添加到压缩事件列表
            step_ctx.compression_events.append(compression_event)
            
            # 输出详细的压缩日志
            logger.info(f"   ✓ History compressed at iteration {step_ctx.iteration}:")
            logger.info(f"      Commands: {total_commands} total → {len(old_commands)} compressed + {len(recent_commands)} kept")
            if token_count_before and token_count_after:
                logger.info(f"      Tokens: {token_count_before} → {token_count_after} ({compression_ratio:.1f}% saved)")
            logger.info(f"      Compressed text: {len(compressed_text)} chars")
            
        except Exception as e:
            logger.error(f"   ✗ Compression failed: {e}, keeping all commands")
        
        return step_ctx
    
    def _format_commands(self, step_ctx: StepContext) -> str:
        """格式化命令历史（支持压缩）"""
        lines = []
        
        # 如果有压缩历史，先添加
        if step_ctx.compressed_history:
            lines.append("=== Earlier Commands (Compressed) ===")
            lines.append(step_ctx.compressed_history)
            lines.append("")
            lines.append("=== Recent Commands (Full Detail) ===")
        
        # 添加最近的完整命令
        if not step_ctx.commands:
            lines.append("(no recent commands)")
        else:
            for i, cmd in enumerate(step_ctx.commands, 1):
                status = "SUCCESS" if cmd.success else f"FAILED"
                lines.append(f"{i}. [{status}] {cmd.command}")
                
                # 完整输出，不再截断
                if cmd.stdout:
                    lines.append(f"   stdout:")
                    for line in cmd.stdout.split('\n'):
                        lines.append(f"     {line}")
                
                if cmd.stderr:
                    lines.append(f"   stderr:")
                    for line in cmd.stderr.split('\n'):
                        lines.append(f"     {line}")
        
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
        """验证并解析步骤产出（简化版）
        
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
        
        # 提取 key_info（可选）
        key_info = outputs_dict.get("key_info", {})
        if not isinstance(key_info, dict):
            logger.warning(f"key_info should be a dict, got {type(key_info)}")
            key_info = {}
        
        try:
            return StepOutputs(
                summary=summary,
                key_info=key_info,
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

