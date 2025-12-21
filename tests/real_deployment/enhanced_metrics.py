"""增强的指标收集系统 - 收集系统信息、LLM配置和重试信息"""
import platform
import psutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any

from auto_deployer.config import AppConfig
from .metrics_collector import ProjectMetrics


@dataclass
class SystemInfo:
    """系统信息"""
    os_name: str  # Windows/Linux/Darwin
    os_version: str  # 系统版本
    python_version: str  # Python版本
    hostname: str  # 主机名
    cpu_count: int  # CPU核心数
    memory_total_gb: float  # 总内存（GB）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class LLMConfig:
    """LLM配置信息"""
    provider: str  # gemini/openai/anthropic等
    model: str  # 模型名称
    temperature: float  # 温度参数
    max_iterations: int  # 最大迭代次数
    max_iterations_per_step: int  # 每步最大迭代次数
    enable_planning: bool  # 是否启用规划模式
    require_plan_approval: bool  # 是否需要计划批准
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class RetryInfo:
    """重试信息"""
    total_attempts: int  # 总尝试次数
    failed_attempts: int  # 失败次数
    final_attempt: int  # 最终成功/失败的尝试次数
    retry_reasons: List[str]  # 重试原因列表
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class EnhancedProjectMetrics:
    """增强的项目测试指标"""
    # 继承自 ProjectMetrics 的字段
    project_name: str
    project_difficulty: str
    success: bool
    final_status: str
    deployment_time_seconds: float
    total_iterations: int
    total_commands: int
    llm_call_count: int
    user_interactions: int
    error_recovery_count: int
    strategy_used: str
    expected_strategy: str
    strategy_correct: Optional[bool]
    verification_passed: bool
    verification_details: List[Dict]
    log_file: Optional[str] = None
    error: Optional[str] = None
    
    # 新增字段
    repo_url: str = ""  # 仓库URL
    system_info: Optional[SystemInfo] = None  # 系统信息
    llm_config: Optional[LLMConfig] = None  # LLM配置
    retry_info: Optional[RetryInfo] = None  # 重试信息
    test_start_time: str = ""  # 测试开始时间
    test_end_time: str = ""  # 测试结束时间
    worker_id: Optional[int] = None  # 执行的worker ID
    task_id: str = ""  # 任务ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "project_name": self.project_name,
            "repo_url": self.repo_url,
            "project_difficulty": self.project_difficulty,
            "success": self.success,
            "final_status": self.final_status,
            "deployment_time_seconds": self.deployment_time_seconds,
            "total_iterations": self.total_iterations,
            "total_commands": self.total_commands,
            "llm_call_count": self.llm_call_count,
            "user_interactions": self.user_interactions,
            "error_recovery_count": self.error_recovery_count,
            "strategy_used": self.strategy_used,
            "expected_strategy": self.expected_strategy,
            "strategy_correct": self.strategy_correct,
            "verification_passed": self.verification_passed,
            "verification_details": self.verification_details,
            "log_file": self.log_file,
            "error": self.error,
            "test_start_time": self.test_start_time,
            "test_end_time": self.test_end_time,
            "worker_id": self.worker_id,
            "task_id": self.task_id,
        }
        
        if self.system_info:
            result["system_info"] = self.system_info.to_dict()
        if self.llm_config:
            result["llm_config"] = self.llm_config.to_dict()
        if self.retry_info:
            result["retry_info"] = self.retry_info.to_dict()
            
        return result


class SystemInfoCollector:
    """系统信息收集器"""
    
    @staticmethod
    def collect_system_info() -> SystemInfo:
        """
        收集系统信息
        
        Returns:
            SystemInfo对象
        """
        return SystemInfo(
            os_name=platform.system(),
            os_version=platform.version(),
            python_version=sys.version.split()[0],
            hostname=platform.node(),
            cpu_count=psutil.cpu_count(logical=True) or 1,
            memory_total_gb=round(psutil.virtual_memory().total / (1024**3), 2)
        )


def collect_llm_config(config: AppConfig) -> LLMConfig:
    """
    从AppConfig中提取LLM配置信息
    
    Args:
        config: Auto-Deployer应用配置
        
    Returns:
        LLMConfig对象
    """
    return LLMConfig(
        provider=config.llm.provider,
        model=config.llm.model,
        temperature=config.llm.temperature,
        max_iterations=config.agent.max_iterations,
        max_iterations_per_step=config.agent.max_iterations_per_step,
        enable_planning=config.agent.use_orchestrator,  # 使用 use_orchestrator 代替
        require_plan_approval=config.agent.require_plan_approval
    )


def enhance_metrics(
    base_metrics: ProjectMetrics,
    repo_url: str,
    system_info: SystemInfo,
    llm_config: LLMConfig,
    retry_info: Optional[RetryInfo],
    test_start_time: datetime,
    test_end_time: datetime,
    worker_id: Optional[int],
    task_id: str
) -> EnhancedProjectMetrics:
    """
    将基础指标增强为包含完整信息的增强指标
    
    Args:
        base_metrics: 基础项目指标
        repo_url: 仓库URL
        system_info: 系统信息
        llm_config: LLM配置
        retry_info: 重试信息
        test_start_time: 测试开始时间
        test_end_time: 测试结束时间
        worker_id: Worker ID
        task_id: 任务ID
        
    Returns:
        EnhancedProjectMetrics对象
    """
    return EnhancedProjectMetrics(
        # 基础字段
        project_name=base_metrics.project_name,
        project_difficulty=base_metrics.project_difficulty,
        success=base_metrics.success,
        final_status=base_metrics.final_status,
        deployment_time_seconds=base_metrics.deployment_time_seconds,
        total_iterations=base_metrics.total_iterations,
        total_commands=base_metrics.total_commands,
        llm_call_count=base_metrics.llm_call_count,
        user_interactions=base_metrics.user_interactions,
        error_recovery_count=base_metrics.error_recovery_count,
        strategy_used=base_metrics.strategy_used,
        expected_strategy=base_metrics.expected_strategy,
        strategy_correct=base_metrics.strategy_correct,
        verification_passed=base_metrics.verification_passed,
        verification_details=base_metrics.verification_details,
        log_file=base_metrics.log_file,
        error=base_metrics.error,
        # 增强字段
        repo_url=repo_url,
        system_info=system_info,
        llm_config=llm_config,
        retry_info=retry_info,
        test_start_time=test_start_time.isoformat(),
        test_end_time=test_end_time.isoformat(),
        worker_id=worker_id,
        task_id=task_id
    )
