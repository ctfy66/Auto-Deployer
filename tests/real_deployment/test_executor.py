"""测试执行器 - 执行单个测试任务并支持重试"""
import logging
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

from auto_deployer.config import AppConfig
from .test_task import TestTask
from .enhanced_metrics import (
    EnhancedProjectMetrics, 
    RetryInfo, 
    SystemInfoCollector,
    collect_llm_config,
    enhance_metrics
)
from .deployment_tester import DeploymentTester
from .metrics_collector import ProjectMetrics, MetricsCollector

logger = logging.getLogger(__name__)


class TestExecutor:
    """测试执行器 - 支持重试逻辑"""
    
    def __init__(self, config: AppConfig, log_dir: Path = Path("tests/results")):
        """
        初始化测试执行器
        
        Args:
            config: Auto-Deployer应用配置
            log_dir: 日志和结果保存目录
        """
        self.config = config
        self.log_dir = Path(log_dir)
        self.tester = DeploymentTester(config, log_dir)
        
        # 收集系统信息（只需收集一次）
        self.system_info = SystemInfoCollector.collect_system_info()
        self.llm_config = collect_llm_config(config)
    
    def execute_with_retry(
        self, 
        task: TestTask, 
        worker_id: Optional[int] = None
    ) -> EnhancedProjectMetrics:
        """
        执行测试任务（带重试逻辑）
        
        Args:
            task: 测试任务
            worker_id: Worker ID（可选）
            
        Returns:
            增强的项目指标
        """
        retry_reasons = []
        failed_attempts = 0
        last_result = None
        
        current_task = task
        
        while True:
            logger.info(
                f"[{current_task.project.name}] 尝试 {current_task.attempt}/{current_task.max_attempts}"
            )
            
            # 执行单次尝试
            result = self._execute_single_attempt(current_task, worker_id)
            last_result = result
            
            # 如果成功，直接返回
            if result.success:
                logger.info(f"[{result.project_name}] ✅ 测试成功")
                break
            
            # 失败，记录失败次数
            failed_attempts += 1
            
            # 判断是否应该重试
            if not current_task.can_retry():
                logger.warning(
                    f"[{result.project_name}] ❌ 测试失败，已达到最大重试次数"
                )
                break
            
            if not self._should_retry(result, current_task):
                logger.warning(
                    f"[{result.project_name}] ❌ 测试失败，错误不可重试"
                )
                break
            
            # 记录重试原因
            error_type = self._classify_error(result.error or "unknown")
            retry_reasons.append(f"Attempt {current_task.attempt}: {error_type}")
            
            logger.info(
                f"[{result.project_name}] 🔄 准备重试 "
                f"(原因: {error_type})"
            )
            
            # 创建下一次重试任务
            current_task = current_task.next_attempt()
            
            # 短暂延迟，避免立即重试
            time.sleep(2)
        
        # 构建重试信息
        retry_info = RetryInfo(
            total_attempts=current_task.attempt,
            failed_attempts=failed_attempts,
            final_attempt=current_task.attempt,
            retry_reasons=retry_reasons
        ) if current_task.attempt > 1 or failed_attempts > 0 else None
        
        # 更新重试信息到结果中
        if last_result:
            last_result.retry_info = retry_info
        
        return last_result
    
    def _execute_single_attempt(
        self, 
        task: TestTask, 
        worker_id: Optional[int]
    ) -> EnhancedProjectMetrics:
        """
        执行单次测试尝试
        
        Args:
            task: 测试任务
            worker_id: Worker ID
            
        Returns:
            增强的项目指标
        """
        test_start_time = datetime.now()
        
        try:
            # 调用现有的 DeploymentTester 执行测试
            metrics_dict = self.tester.test_project(
                project=task.project,
                env_config=task.env_config,
                local_mode=task.local_mode
            )
            
            # 转换为 ProjectMetrics
            base_metrics = MetricsCollector.convert_dict_to_metrics(metrics_dict)
            
        except Exception as e:
            logger.error(
                f"[{task.project.name}] 执行异常: {e}", 
                exc_info=True
            )
            
            # 创建失败的指标
            base_metrics = ProjectMetrics(
                project_name=task.project.name,
                project_difficulty=task.project.difficulty,
                success=False,
                final_status="error",
                deployment_time_seconds=0.0,
                total_iterations=0,
                total_commands=0,
                llm_call_count=0,
                user_interactions=0,
                error_recovery_count=0,
                strategy_used="unknown",
                expected_strategy=task.project.expected_strategy,
                strategy_correct=None,
                verification_passed=False,
                verification_details=[],
                error=str(e)
            )
        
        test_end_time = datetime.now()
        
        # 增强指标
        enhanced = enhance_metrics(
            base_metrics=base_metrics,
            repo_url=task.project.repo_url,
            system_info=self.system_info,
            llm_config=self.llm_config,
            retry_info=None,  # 稍后在 execute_with_retry 中设置
            test_start_time=test_start_time,
            test_end_time=test_end_time,
            worker_id=worker_id,
            task_id=task.task_id
        )
        
        return enhanced
    
    def _should_retry(
        self, 
        result: EnhancedProjectMetrics, 
        task: TestTask
    ) -> bool:
        """
        判断是否应该重试
        
        Args:
            result: 测试结果
            task: 测试任务
            
        Returns:
            是否应该重试
        """
        if not task.can_retry():
            return False
        
        # 如果没有错误信息，不重试
        if not result.error:
            return False
        
        # 分类错误
        error_type = self._classify_error(result.error)
        
        # 只有可重试的错误才重试
        return error_type == "retryable"
    
    def _classify_error(self, error_message: str) -> str:
        """
        分类错误类型
        
        Args:
            error_message: 错误信息
            
        Returns:
            错误类型: retryable/config_error/project_error/verification_error
        """
        error_lower = error_message.lower()
        
        # 可重试的错误
        retryable_keywords = [
            "timeout", "timed out",
            "connection", "connect",
            "network", "dns",
            "rate limit", "too many requests",
            "temporary", "temporarily",
            "unavailable", "503", "502", "504",
            "resource", "memory",
        ]
        
        for keyword in retryable_keywords:
            if keyword in error_lower:
                return "retryable"
        
        # 配置错误（不可重试）
        config_keywords = [
            "api key", "apikey", "api_key",
            "authentication", "auth",
            "unauthorized", "401",
            "forbidden", "403",
            "invalid key", "invalid token",
        ]
        
        for keyword in config_keywords:
            if keyword in error_lower:
                return "config_error"
        
        # 项目错误（不可重试）
        project_keywords = [
            "repository not found", "repo not found",
            "not found", "404",
            "clone failed", "git clone",
            "permission denied",
        ]
        
        for keyword in project_keywords:
            if keyword in error_lower:
                return "project_error"
        
        # 验证错误（不可重试）
        verification_keywords = [
            "verification failed",
            "application failed to start",
            "service not responding",
        ]
        
        for keyword in verification_keywords:
            if keyword in error_lower:
                return "verification_error"
        
        # 默认为可重试（保守策略）
        return "retryable"


def execute_test_task(
    task: TestTask, 
    config: AppConfig,
    worker_id: Optional[int] = None,
    log_dir: Path = Path("tests/results")
) -> EnhancedProjectMetrics:
    """
    执行测试任务的独立函数（用于进程池调用）
    
    Args:
        task: 测试任务
        config: Auto-Deployer配置
        worker_id: Worker ID
        log_dir: 日志目录
        
    Returns:
        增强的项目指标
    """
    executor = TestExecutor(config, log_dir)
    return executor.execute_with_retry(task, worker_id)
