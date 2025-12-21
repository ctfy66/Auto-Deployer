"""并行测试运行器 - 使用进程池并行执行测试"""
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed, Future
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from auto_deployer.config import AppConfig
from .test_task import TestTask
from .test_projects import TestProject
from .enhanced_metrics import EnhancedProjectMetrics, SystemInfoCollector, collect_llm_config
from .test_executor import execute_test_task

logger = logging.getLogger(__name__)


class ParallelTestRunner:
    """并行测试运行器"""
    
    def __init__(
        self,
        config: AppConfig,
        max_workers: int = 3,
        retry_on_failure: bool = True,
        retry_max_attempts: int = 1,
        timeout_per_project: int = 30,
        log_dir: Path = Path("tests/results")
    ):
        """
        初始化并行测试运行器
        
        Args:
            config: Auto-Deployer配置
            max_workers: 最大并行worker数（默认3）
            retry_on_failure: 是否在失败时重试（默认True）
            retry_max_attempts: 最大重试次数（默认1，即最多尝试2次）
            timeout_per_project: 单个项目超时时间（分钟，默认30）
            log_dir: 日志目录
        """
        self.config = config
        self.max_workers = max_workers
        self.retry_on_failure = retry_on_failure
        self.retry_max_attempts = retry_max_attempts + 1  # 转换为总尝试次数
        self.timeout_per_project = timeout_per_project
        self.log_dir = Path(log_dir)
        
        logger.info(f"🚀 初始化并行测试运行器")
        logger.info(f"   并行度: {self.max_workers} workers")
        logger.info(f"   重试策略: {'启用' if self.retry_on_failure else '禁用'}")
        if self.retry_on_failure:
            logger.info(f"   最大重试次数: {retry_max_attempts}")
    
    def run_tests(
        self,
        projects: List[TestProject],
        env_config: Dict[str, Any],
        local_mode: bool = True
    ) -> List[EnhancedProjectMetrics]:
        """
        并行运行所有测试
        
        Args:
            projects: 测试项目列表
            env_config: 环境配置
            local_mode: 是否使用本地模式
            
        Returns:
            增强的项目指标列表
        """
        if not projects:
            logger.warning("⚠️  没有项目需要测试")
            return []
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📋 准备测试 {len(projects)} 个项目")
        logger.info(f"{'='*60}\n")
        
        # 创建任务列表
        tasks = self._create_tasks(projects, env_config, local_mode)
        
        # 并行执行
        results = self._execute_parallel(tasks)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ 所有测试完成")
        logger.info(f"{'='*60}\n")
        
        return results
    
    def _create_tasks(
        self,
        projects: List[TestProject],
        env_config: Dict[str, Any],
        local_mode: bool
    ) -> List[TestTask]:
        """
        从项目列表创建测试任务
        
        Args:
            projects: 项目列表
            env_config: 环境配置
            local_mode: 本地模式
            
        Returns:
            任务列表
        """
        tasks = []
        for project in projects:
            task = TestTask(
                project=project,
                env_config=env_config,
                local_mode=local_mode,
                attempt=1,
                max_attempts=self.retry_max_attempts if self.retry_on_failure else 1
            )
            tasks.append(task)
        
        return tasks
    
    def _execute_parallel(
        self,
        tasks: List[TestTask]
    ) -> List[EnhancedProjectMetrics]:
        """
        并行执行任务
        
        Args:
            tasks: 任务列表
            
        Returns:
            结果列表
        """
        total_tasks = len(tasks)
        results: List[EnhancedProjectMetrics] = []
        completed_count = 0
        
        # 创建进程池
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_task: Dict[Future, TestTask] = {}
            
            for i, task in enumerate(tasks):
                future = executor.submit(
                    execute_test_task,
                    task=task,
                    config=self.config,
                    worker_id=(i % self.max_workers) + 1,
                    log_dir=self.log_dir
                )
                future_to_task[future] = task
            
            # 使用 as_completed 实时获取完成的任务
            try:
                for future in as_completed(
                    future_to_task, 
                    timeout=self.timeout_per_project * 60 * total_tasks
                ):
                    task = future_to_task[future]
                    completed_count += 1
                    
                    try:
                        result = future.result(timeout=self.timeout_per_project * 60)
                        results.append(result)
                        
                        # 打印进度
                        self._print_progress(completed_count, total_tasks, result)
                        
                    except Exception as e:
                        logger.error(
                            f"[{task.project.name}] ❌ 任务执行异常: {e}",
                            exc_info=True
                        )
                        
                        # 创建失败结果
                        from .metrics_collector import ProjectMetrics
                        from .enhanced_metrics import enhance_metrics
                        
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
                        
                        enhanced = enhance_metrics(
                            base_metrics=base_metrics,
                            repo_url=task.project.repo_url,
                            system_info=SystemInfoCollector.collect_system_info(),
                            llm_config=collect_llm_config(self.config),
                            retry_info=None,
                            test_start_time=datetime.now(),
                            test_end_time=datetime.now(),
                            worker_id=None,
                            task_id=task.task_id
                        )
                        
                        results.append(enhanced)
                        self._print_progress(completed_count, total_tasks, enhanced)
            
            except KeyboardInterrupt:
                logger.warning("\n⚠️  测试被用户中断")
                executor.shutdown(wait=False, cancel_futures=True)
                raise
        
        return results
    
    def _print_progress(
        self,
        completed: int,
        total: int,
        result: EnhancedProjectMetrics
    ):
        """
        打印测试进度
        
        Args:
            completed: 已完成数量
            total: 总数量
            result: 测试结果
        """
        status_icon = "✅" if result.success else "❌"
        
        # 基本信息
        info_parts = [
            f"[{completed}/{total}]",
            f"{status_icon}",
            f"{result.project_name}:"
        ]
        
        # 详细信息
        details = []
        if result.success:
            details.append(f"成功")
        else:
            details.append(f"失败")
        
        details.append(f"{result.deployment_time_seconds:.1f}s")
        details.append(f"{result.total_iterations} 迭代")
        
        # 重试信息
        if result.retry_info and result.retry_info.total_attempts > 1:
            details.append(
                f"🔄 重试 {result.retry_info.failed_attempts}次"
            )
        
        # 错误信息（如果失败）
        if not result.success and result.error:
            # 只显示错误的前50个字符
            error_preview = result.error[:50]
            if len(result.error) > 50:
                error_preview += "..."
            details.append(f"({error_preview})")
        
        info_parts.append(", ".join(details))
        
        logger.info(" ".join(info_parts))
