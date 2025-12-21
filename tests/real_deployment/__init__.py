"""真实部署测试模块"""
from .test_projects import TEST_PROJECTS, TestProject, VerificationConfig
from .metrics_collector import MetricsCollector, ProjectMetrics
from .report_generator import ReportGenerator

# 新增：并行测试模块
from .test_task import TestTask
from .enhanced_metrics import (
    EnhancedProjectMetrics,
    SystemInfo,
    LLMConfig,
    RetryInfo,
    SystemInfoCollector,
    collect_llm_config,
    enhance_metrics
)
from .test_executor import TestExecutor, execute_test_task
from .parallel_runner import ParallelTestRunner
from .enhanced_report_generator import EnhancedReportGenerator

# 延迟导入需要docker的模块
def _lazy_import():
    """延迟导入需要docker的模块"""
    from .test_environment import TestEnvironment
    from .local_test_environment import LocalTestEnvironment
    from .deployment_tester import DeploymentTester
    from .test_suite import run_test_suite, run_parallel_test_suite
    return TestEnvironment, LocalTestEnvironment, DeploymentTester, run_test_suite, run_parallel_test_suite

__all__ = [
    "TEST_PROJECTS",
    "TestProject",
    "VerificationConfig",
    "MetricsCollector",
    "ProjectMetrics",
    "ReportGenerator",
    # 并行测试
    "TestTask",
    "EnhancedProjectMetrics",
    "SystemInfo",
    "LLMConfig",
    "RetryInfo",
    "SystemInfoCollector",
    "collect_llm_config",
    "enhance_metrics",
    "TestExecutor",
    "execute_test_task",
    "ParallelTestRunner",
    "EnhancedReportGenerator",
    "_lazy_import",
]

