"""真实部署测试模块"""
from .test_projects import TEST_PROJECTS, TestProject, VerificationConfig
from .metrics_collector import MetricsCollector, ProjectMetrics
from .report_generator import ReportGenerator

# 延迟导入需要docker的模块
def _lazy_import():
    """延迟导入需要docker的模块"""
    from .test_environment import TestEnvironment
    from .local_test_environment import LocalTestEnvironment
    from .deployment_tester import DeploymentTester
    from .test_suite import run_test_suite
    return TestEnvironment, LocalTestEnvironment, DeploymentTester, run_test_suite

__all__ = [
    "TEST_PROJECTS",
    "TestProject",
    "VerificationConfig",
    "MetricsCollector",
    "ProjectMetrics",
    "ReportGenerator",
    "_lazy_import",
]

