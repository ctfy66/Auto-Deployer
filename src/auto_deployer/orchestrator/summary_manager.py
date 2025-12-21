"""Summary manager for maintaining global execution context.

This module manages the ExecutionSummary that tracks deployment progress
and provides context for subsequent steps without passing full history.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from .models import ExecutionSummary, StepOutputs

if TYPE_CHECKING:
    from ..llm.agent import DeploymentStep

logger = logging.getLogger(__name__)


class SummaryManager:
    """管理执行摘要的更新和大小控制
    
    职责：
    1. 初始化和维护 ExecutionSummary
    2. 合并每个步骤的产出到全局摘要
    3. 控制摘要大小，防止 Token 爆炸
    """
    
    # 摘要大小限制
    MAX_COMPLETED_ACTIONS = 15
    MAX_RESOLVED_ISSUES = 5
    MAX_ENVIRONMENT_KEYS = 30
    MAX_CONFIGURATION_KEYS = 20
    
    def __init__(
        self,
        project_name: str,
        deploy_dir: str,
        strategy: str,
    ) -> None:
        """初始化摘要管理器
        
        Args:
            project_name: 项目名称
            deploy_dir: 部署目录
            strategy: 部署策略
        """
        self.summary = ExecutionSummary(
            project_name=project_name,
            deploy_dir=deploy_dir,
            strategy=strategy,
            last_updated=datetime.now().isoformat(),
        )
        logger.debug(
            "SummaryManager initialized for %s (strategy: %s)", 
            project_name, 
            strategy
        )
    
    def merge_step_outputs(
        self,
        step_name: str,
        step_category: str,
        outputs: StepOutputs,
    ) -> None:
        """将步骤产出合并到全局摘要（简化版）
        
        Args:
            step_name: 步骤名称
            step_category: 步骤类别
            outputs: 步骤的结构化产出
        """
        # 1. 添加完成动作
        action_summary = f"[{step_category.upper()}] {step_name}: {outputs.summary}"
        self.summary.completed_actions.append(action_summary)
        logger.debug("Added completed action: %s", action_summary)
        
        # 2. 合并关键信息到环境（如果有）
        if outputs.key_info:
            self.summary.environment.update(outputs.key_info)
            logger.debug(
                "Updated environment with %d key info items", 
                len(outputs.key_info)
            )
        
        # 3. 更新时间戳
        self.summary.last_updated = datetime.now().isoformat()
        
        # 4. 控制摘要大小
        self._truncate_if_needed()
    
    def _truncate_if_needed(self) -> None:
        """控制摘要大小，防止无限增长"""
        # 截断已完成动作
        if len(self.summary.completed_actions) > self.MAX_COMPLETED_ACTIONS:
            removed = len(self.summary.completed_actions) - self.MAX_COMPLETED_ACTIONS
            self.summary.completed_actions = self.summary.completed_actions[-self.MAX_COMPLETED_ACTIONS:]
            logger.debug("Truncated completed_actions, removed %d old entries", removed)
        
        # 截断已解决问题
        if len(self.summary.resolved_issues) > self.MAX_RESOLVED_ISSUES:
            removed = len(self.summary.resolved_issues) - self.MAX_RESOLVED_ISSUES
            self.summary.resolved_issues = self.summary.resolved_issues[-self.MAX_RESOLVED_ISSUES:]
            logger.debug("Truncated resolved_issues, removed %d old entries", removed)
        
        # 环境变量太多时发出警告（但不截断，因为可能都是必要的）
        if len(self.summary.environment) > self.MAX_ENVIRONMENT_KEYS:
            logger.warning(
                "Environment has %d keys, consider cleanup",
                len(self.summary.environment)
            )
        
        # 配置值太多时发出警告
        if len(self.summary.configurations) > self.MAX_CONFIGURATION_KEYS:
            logger.warning(
                "Configurations has %d keys, consider cleanup",
                len(self.summary.configurations)
            )
    
    def update_environment(self, key: str, value: Any) -> None:
        """直接更新环境变量
        
        Args:
            key: 环境变量名
            value: 值
        """
        self.summary.environment[key] = value
        self.summary.last_updated = datetime.now().isoformat()
    
    def update_configuration(self, key: str, value: str) -> None:
        """直接更新配置值
        
        Args:
            key: 配置名
            value: 值
        """
        self.summary.configurations[key] = value
        self.summary.last_updated = datetime.now().isoformat()
    
    def add_resolved_issue(self, issue: str, resolution: str) -> None:
        """添加已解决的问题
        
        Args:
            issue: 问题描述
            resolution: 解决方案
        """
        self.summary.resolved_issues.append({
            "issue": issue,
            "resolution": resolution,
        })
        self._truncate_if_needed()
        self.summary.last_updated = datetime.now().isoformat()
    
    def get_summary(self) -> ExecutionSummary:
        """获取当前摘要"""
        return self.summary
    
    def get_prompt_context(self) -> str:
        """获取用于 LLM prompt 的摘要文本"""
        return self.summary.to_prompt_context()
    
    def update_strategy(self, new_strategy: str) -> None:
        """更新部署策略（当运行时需要切换策略时）
        
        Args:
            new_strategy: 新的部署策略
        """
        old_strategy = self.summary.strategy
        self.summary.strategy = new_strategy
        self.summary.last_updated = datetime.now().isoformat()
        
        # 记录策略变更
        self.summary.resolved_issues.append({
            "issue": f"Strategy change required from {old_strategy}",
            "resolution": f"Switched to {new_strategy}",
        })
        self._truncate_if_needed()
        
        logger.info("Strategy updated: %s -> %s", old_strategy, new_strategy)
