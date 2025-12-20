"""Deployment orchestrator: Coordinates the execution of deployment plans."""

from __future__ import annotations

import json
import logging
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, Union, List, Dict, TYPE_CHECKING

from .models import (
    StepContext, StepResult, StepStatus, DeployContext, StepOutputs, ExecutionSummary
)
from .step_executor import StepExecutor
from .summary_manager import SummaryManager

if TYPE_CHECKING:
    from ..llm.agent import DeploymentPlan, DeploymentStep
    from ..ssh import SSHSession
    from ..local import LocalSession
    from ..interaction import UserInteractionHandler
    from ..config import LLMConfig

logger = logging.getLogger(__name__)


class DeploymentOrchestrator:
    """
    部署编排器
    
    按顺序执行 DeploymentPlan 中的每个步骤，
    使用 StepExecutor 执行单个步骤。
    """
    
    def __init__(
        self,
        llm_config: "LLMConfig",
        session: Union["SSHSession", "LocalSession"],
        interaction_handler: "UserInteractionHandler",
        log_dir: Optional[str] = None,
        max_iterations_per_step: int = 10,
        is_windows: bool = False,
    ):
        self.llm_config = llm_config
        self.session = session
        self.interaction_handler = interaction_handler
        self.log_dir = Path(log_dir) if log_dir else Path.cwd() / "agent_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.is_windows = is_windows
        
        self.step_executor = StepExecutor(
            llm_config=llm_config,
            session=session,
            interaction_handler=interaction_handler,
            max_iterations_per_step=max_iterations_per_step,
            is_windows=is_windows,
            on_command_executed=lambda: self._save_log(),
        )
        
        # 摘要管理器（在 run() 中初始化）
        self.summary_manager: Optional[SummaryManager] = None
        
        # 日志
        self.deployment_log: dict = {}
        self.current_log_file: Optional[Path] = None
    
    def run(
        self,
        plan: "DeploymentPlan",
        deploy_ctx: DeployContext,
    ) -> bool:
        """
        执行部署计划
        
        Args:
            plan: 部署计划
            deploy_ctx: 部署上下文
            
        Returns:
            bool: 部署是否成功
        """
        # 初始化日志
        self._init_log(deploy_ctx, plan)
        
        # 初始化摘要管理器
        project_name = deploy_ctx.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        self.summary_manager = SummaryManager(
            project_name=project_name,
            deploy_dir=deploy_ctx.deploy_dir,
            strategy=plan.strategy,
        )
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("🚀 DEPLOYMENT ORCHESTRATION")
        logger.info("=" * 60)
        logger.info(f"Strategy: {plan.strategy}")
        logger.info(f"Total Steps: {len(plan.steps)}")
        if plan.estimated_time:
            logger.info(f"Estimated Time: {plan.estimated_time}")
        logger.info("")
        
        # 显示步骤概览
        logger.info("Steps:")
        for i, step in enumerate(plan.steps, 1):
            logger.info(f"  {i}. [{step.category.upper()}] {step.name}")
        logger.info("")
        logger.info("=" * 60)
        logger.info("")
        
        # 记录计划
        self.deployment_log["plan"] = plan.to_dict()
        self._save_log()
        
        # 收集已完成步骤的结构化产出（用于传递给后续步骤）
        completed_outputs: Dict[int, StepOutputs] = {}
        
        # 按顺序执行每个步骤
        for i, step in enumerate(plan.steps):
            step_ctx = self._create_step_context(step, completed_outputs)
            
            logger.info(f"📍 Step {i + 1}/{len(plan.steps)}: {step.name}")
            logger.info(f"   Category: {step.category}")
            
            # 检查依赖
            if not self._check_dependencies(step, deploy_ctx):
                logger.warning(f"   ⚠️ Skipping: dependency not met")
                step_ctx.status = StepStatus.SKIPPED
                result = StepResult.skipped("Dependency not met")
                deploy_ctx.step_results[step.id] = result
                self._log_step_result(step, step_ctx, result)
                logger.info("")
                continue
            
            # 创建步骤日志条目（先标记为 running）
            step_log = {
                "step_id": step.id,
                "step_name": step.name,
                "category": step.category,
                "status": "running",
                "iterations": 0,
                "compressed": False,
                "compressed_history": None,
                "commands": [],
                "user_interactions": [],
                "outputs": {},
                "structured_outputs": None,
                "error": None,
                "timestamp": datetime.now().isoformat(),
            }
            self.deployment_log["steps"].append(step_log)
            self._save_log()
            
            # 执行步骤
            result = self.step_executor.execute(step_ctx, deploy_ctx)
            
            # 记录结果
            deploy_ctx.step_results[step.id] = result
            self._log_step_result(step, step_ctx, result)
            
            # 处理失败
            if result.status == StepStatus.FAILED:
                user_choice = self._handle_failure(step, result)
                
                if user_choice == "retry":
                    logger.info(f"   🔄 Retrying step...")
                    # 重置并重试
                    step_ctx = self._create_step_context(step, completed_outputs)
                    result = self.step_executor.execute(step_ctx, deploy_ctx)
                    deploy_ctx.step_results[step.id] = result
                    self._log_step_result(step, step_ctx, result)
                    
                    if result.status == StepStatus.FAILED:
                        logger.error(f"   ❌ Retry failed, aborting")
                        self._finalize_log("failed")
                        return False
                        
                elif user_choice == "skip":
                    logger.info(f"   ⏭️ Skipping step")
                    deploy_ctx.step_results[step.id] = StepResult.skipped("User skipped")
                    logger.info("")
                    continue
                    
                else:  # abort
                    logger.error(f"   ❌ User aborted deployment")
                    self._finalize_log("aborted")
                    return False
            
            # 合并结构化产出到摘要
            if result.structured_outputs:
                self.summary_manager.merge_step_outputs(
                    step_name=step.name,
                    step_category=step.category,
                    outputs=result.structured_outputs,
                )
                completed_outputs[step.id] = result.structured_outputs
                logger.debug(f"   📦 Merged outputs to summary: {result.structured_outputs.summary}")
            
            # 传递输出到共享上下文（保持向后兼容）
            if result.outputs:
                deploy_ctx.shared_data.update(result.outputs)
                logger.debug(f"   Outputs: {result.outputs}")
            
            logger.info("")
        
        # 全部完成
        logger.info("=" * 60)
        logger.info("🎉 Deployment completed successfully!")
        logger.info("=" * 60)
        
        # 记录最终摘要
        if self.summary_manager:
            self.deployment_log["execution_summary"] = self.summary_manager.get_summary().to_dict()
        
        self._finalize_log("success")
        return True
    
    def _create_step_context(
        self, 
        step: "DeploymentStep",
        completed_outputs: Optional[Dict[int, StepOutputs]] = None,
    ) -> StepContext:
        """创建步骤上下文
        
        Args:
            step: 部署步骤
            completed_outputs: 已完成步骤的结构化产出
            
        Returns:
            StepContext 步骤上下文
        """
        # 获取前置步骤的产出（只传递直接依赖的步骤产出）
        predecessor_outputs: Dict[int, StepOutputs] = {}
        if completed_outputs and step.depends_on:
            for dep_id in step.depends_on:
                if dep_id in completed_outputs:
                    predecessor_outputs[dep_id] = completed_outputs[dep_id]
        
        # 获取执行摘要
        execution_summary = None
        if self.summary_manager:
            execution_summary = self.summary_manager.get_summary()
        
        return StepContext(
            step_id=step.id,
            step_name=step.name,
            goal=step.description or step.name,
            success_criteria=step.success_criteria or f"Complete: {step.name}",
            category=step.category,
            execution_summary=execution_summary,
            predecessor_outputs=predecessor_outputs,
        )
    
    def _check_dependencies(
        self,
        step: "DeploymentStep",
        deploy_ctx: DeployContext,
    ) -> bool:
        """检查步骤依赖是否满足"""
        if not step.depends_on:
            return True
            
        for dep_id in step.depends_on:
            dep_result = deploy_ctx.step_results.get(dep_id)
            if not dep_result:
                logger.debug(f"   Dependency {dep_id} not executed yet")
                return False
            if dep_result.status not in (StepStatus.SUCCESS, StepStatus.SKIPPED):
                logger.debug(f"   Dependency {dep_id} not successful: {dep_result.status}")
                return False
        return True
    
    def _handle_failure(
        self,
        step: "DeploymentStep",
        result: StepResult,
    ) -> str:
        """处理步骤失败，询问用户"""
        from ..interaction import InteractionRequest, InputType, QuestionCategory
        
        request = InteractionRequest(
            question=f"Step '{step.name}' failed: {result.error}\nWhat would you like to do?",
            options=["Retry this step", "Skip and continue", "Abort deployment"],
            input_type=InputType.CHOICE,
            category=QuestionCategory.ERROR_RECOVERY,
            allow_custom=True,
        )
        response = self.interaction_handler.ask(request)
        
        if response.cancelled or "Abort" in (response.value or ""):
            return "abort"
        elif "Retry" in (response.value or ""):
            return "retry"
        else:
            return "skip"
    
    def _init_log(self, deploy_ctx: DeployContext, plan: "DeploymentPlan") -> None:
        """初始化日志文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        repo_name = deploy_ctx.repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        filename = f"deploy_{repo_name}_{timestamp}.json"
        self.current_log_file = self.log_dir / filename
        
        self.deployment_log = {
            "version": "2.0",  # 新的日志格式版本
            "mode": "orchestrator",
            "repo_url": deploy_ctx.repo_url,
            "deploy_dir": deploy_ctx.deploy_dir,
            "project_type": deploy_ctx.project_type,
            "framework": deploy_ctx.framework,
            "host_info": deploy_ctx.host_info,  # 保存主机信息
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "running",
            "config": {
                "model": self.llm_config.model,
                "temperature": self.llm_config.temperature,
                "max_iterations_per_step": self.step_executor.max_iterations,
            },
            "plan": None,
            "steps": [],
        }
        
        logger.info(f"📝 Logging to: {self.current_log_file}")
    
    def _log_step_result(
        self,
        step: "DeploymentStep",
        step_ctx: StepContext,
        result: StepResult,
    ) -> None:
        """更新步骤日志结果（更新最后一个步骤条目）"""
        # 获取最后一个步骤条目（应该已经在 run() 中创建）
        if not self.deployment_log["steps"]:
            # 如果没有条目，创建一个（兼容性处理）
            step_log = {
                "step_id": step.id,
                "step_name": step.name,
                "category": step.category,
            }
            self.deployment_log["steps"].append(step_log)
        
        step_log = self.deployment_log["steps"][-1]
        
        # 更新状态和结果
        step_log["status"] = result.status.value
        step_log["iterations"] = step_ctx.iteration
        step_log["compressed"] = step_ctx.compressed_history is not None
        step_log["compressed_history"] = step_ctx.compressed_history if step_ctx.compressed_history else None
        
        # 添加压缩事件记录
        compression_events_log = []
        for event in step_ctx.compression_events:
            compression_events_log.append(event.to_dict())
        step_log["compression_events"] = compression_events_log
        
        # 更新命令历史
        commands_log = []
        for cmd in step_ctx.commands:
            commands_log.append({
                "command": cmd.command,
                "success": cmd.success,
                "exit_code": cmd.exit_code,
                "stdout": cmd.stdout[:1000] if cmd.stdout and len(cmd.stdout) > 1000 else cmd.stdout,
                "stderr": cmd.stderr[:500] if cmd.stderr and len(cmd.stderr) > 500 else cmd.stderr,
                "timestamp": cmd.timestamp,
            })
        step_log["commands"] = commands_log
        
        # 更新用户交互
        step_log["user_interactions"] = step_ctx.user_interactions
        
        # 更新输出
        step_log["outputs"] = result.outputs or {}
        
        # 更新结构化输出
        structured_outputs_dict = None
        if result.structured_outputs:
            structured_outputs_dict = result.structured_outputs.to_dict()
        step_log["structured_outputs"] = structured_outputs_dict
        
        # 更新错误
        step_log["error"] = result.error
        
        # 更新时间戳（完成时间）
        step_log["timestamp"] = datetime.now().isoformat()
        
        # 保存日志
        self._save_log()
    
    def _finalize_log(self, status: str) -> None:
        """完成日志记录"""
        self.deployment_log["end_time"] = datetime.now().isoformat()
        self.deployment_log["status"] = status
        
        # 计算统计信息
        total_commands = sum(
            len(s.get("commands", [])) 
            for s in self.deployment_log.get("steps", [])
        )
        successful_steps = sum(
            1 for s in self.deployment_log.get("steps", [])
            if s.get("status") == "success"
        )
        
        self.deployment_log["summary"] = {
            "total_steps": len(self.deployment_log.get("steps", [])),
            "successful_steps": successful_steps,
            "total_commands": total_commands,
            "duration_seconds": self._calculate_duration(),
        }
        
        self._save_log()
        logger.info(f"📄 Log saved to: {self.current_log_file}")
    
    def _calculate_duration(self) -> float:
        """计算执行时长"""
        try:
            start = datetime.fromisoformat(self.deployment_log["start_time"])
            end = datetime.fromisoformat(self.deployment_log["end_time"])
            return (end - start).total_seconds()
        except Exception:
            return 0.0
    
    def _save_log(self) -> None:
        """保存日志到文件"""
        if self.current_log_file:
            with open(self.current_log_file, "w", encoding="utf-8") as f:
                json.dump(self.deployment_log, f, indent=2, ensure_ascii=False)

