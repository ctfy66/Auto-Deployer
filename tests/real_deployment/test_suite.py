"""测试套件主运行器 - 运行完整的真实部署测试套件"""
import json
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from auto_deployer.config import AppConfig, load_config

from .test_projects import (
    TEST_PROJECTS, 
    TestProject, 
    get_projects_by_difficulty,
    get_projects_by_tag,
    get_all_projects
)
from .test_environment import TestEnvironment
from .local_test_environment import LocalTestEnvironment
from .deployment_tester import DeploymentTester
from .metrics_collector import MetricsCollector, ProjectMetrics
from .report_generator import ReportGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_test_suite(
    config_path: Optional[str] = None,
    project_filter: Optional[str] = None,
    difficulty_filter: Optional[str] = None,
    skip_setup: bool = False,
    local_mode: bool = True
) -> tuple[List[ProjectMetrics], Dict[str, Any]]:
    """
    运行完整的测试套件
    
    Args:
        config_path: 配置文件路径（可选）
        project_filter: 项目名称过滤（可选）
        difficulty_filter: 难度过滤（可选）
        skip_setup: 跳过环境设置（用于调试）
        local_mode: 使用本地测试模式（True=本地，False=Docker容器）
        
    Returns:
        (结果列表, 报告摘要) 元组
    """
    # 1. 加载配置
    logger.info("🚀 开始真实部署测试套件")
    
    # 显示测试模式
    mode_name = "本地测试模式 🏠" if local_mode else "Docker 容器测试模式 🐳"
    logger.info(f"   测试模式: {mode_name}")
    try:
        if config_path:
            config = load_config(config_path)
        else:
            config = load_config()  # 使用默认配置文件 config/default_config.json
    except FileNotFoundError:
        # 如果配置文件不存在，使用代码默认值（不推荐，但为了兼容性保留）
        logger.warning("⚠️  配置文件不存在，使用代码默认值")
        config = AppConfig()
    
    logger.info(f"   使用模型: {config.llm.model}")
    logger.info(f"   温度: {config.llm.temperature}")
    
    # 2. 筛选测试项目
    if project_filter:
        projects = [p for p in TEST_PROJECTS if p.name == project_filter and not p.skip]
        if not projects:
            logger.error(f"❌ 未找到项目: {project_filter}")
            return [], {}
    elif difficulty_filter:
        projects = get_projects_by_difficulty(difficulty_filter)
        logger.info(f"   筛选难度: {difficulty_filter}")
    else:
        projects = get_all_projects()
    
    if not projects:
        logger.error("❌ 没有可测试的项目")
        return [], {}
    
    logger.info(f"   测试项目数: {len(projects)}")
    for p in projects:
        logger.info(f"     - {p.name} ({p.difficulty})")
    logger.info("")
    
    # 3. 创建测试环境
    if local_mode:
        # 本地测试模式
        env = LocalTestEnvironment()
        logger.info("🏠 使用本地测试环境")
    else:
        # Docker 容器测试模式
        env = TestEnvironment()
        logger.info("🐳 使用 Docker 容器测试环境")
    
    env_config = None
    
    if not skip_setup:
        try:
            env_config = env.setup()
        except Exception as e:
            logger.error(f"❌ 环境设置失败: {e}")
            return [], {}
    else:
        logger.warning("⚠️  跳过环境设置（调试模式）")
        # 使用默认配置（需要手动提供）
        env_config = {
            "host": "localhost",
            "port": 2222,
            "username": "root",
            "password": "testpass"
        }
    
    # 4. 创建测试器
    tester = DeploymentTester(config)
    
    # 5. 运行所有测试
    results: List[ProjectMetrics] = []
    
    for i, project in enumerate(projects, 1):
        logger.info(f"\n[{i}/{len(projects)}] 测试项目: {project.name}")
        
        try:
            # 执行测试
            metrics_dict = tester.test_project(
                project, 
                env_config,
                local_mode=local_mode
            )
            
            # 转换为ProjectMetrics对象
            metrics = MetricsCollector.convert_dict_to_metrics(metrics_dict)
            results.append(metrics)
            
            # 打印结果
            status = "✅" if metrics.success else "❌"
            logger.info(
                f"{status} {project.name}: "
                f"成功={metrics.success}, "
                f"耗时={metrics.deployment_time_seconds:.1f}s, "
                f"迭代={metrics.total_iterations}"
            )
            
            # 如果需要，每个测试后清理环境
            # env.reset()
            
        except Exception as e:
            logger.error(f"❌ {project.name}: 测试失败 - {e}", exc_info=True)
            results.append(
                ProjectMetrics(
                    project_name=project.name,
                    project_difficulty=project.difficulty,
                    success=False,
                    final_status="error",
                    deployment_time_seconds=0.0,
                    total_iterations=0,
                    total_commands=0,
                    llm_call_count=0,
                    user_interactions=0,
                    error_recovery_count=0,
                    strategy_used="unknown",
                    expected_strategy=project.expected_strategy,
                    strategy_correct=None,
                    verification_passed=False,
                    verification_details=[],
                    error=str(e)
                )
            )
    
    # 6. 收集结果并生成报告
    summary = MetricsCollector.aggregate_metrics(results)
    
    # 7. 生成报告
    report_gen = ReportGenerator()
    
    config_dict = {
        "model": config.llm.model,
        "temperature": config.llm.temperature,
        "max_iterations": config.agent.max_iterations,
    }
    
    json_report = report_gen.generate_json_report(results, summary, config_dict)
    md_report = report_gen.generate_markdown_report(results, summary)
    
    logger.info(f"\n📊 测试报告已保存:")
    logger.info(f"   JSON: {json_report}")
    logger.info(f"   Markdown: {md_report}")
    
    # 8. 打印摘要
    report_gen.print_summary(summary)
    
    # 9. 清理环境
    if not skip_setup:
        env.cleanup()
    
    return results, summary


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="运行Auto-Deployer真实部署测试套件"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径"
    )
    parser.add_argument(
        "--project",
        type=str,
        help="只测试指定项目（项目名称）"
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        choices=["easy", "medium", "hard"],
        help="只测试指定难度的项目"
    )
    parser.add_argument(
        "--skip-setup",
        action="store_true",
        help="跳过环境设置（调试模式）"
    )
    parser.add_argument(
        "--local",
        action="store_true",
        default=False,
        help="使用本地测试模式（推荐，避免 Docker in Docker 问题）"
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="使用 Docker 容器测试模式（需要完全隔离时使用）"
    )
    
    args = parser.parse_args()
    
    # 确定测试模式：显式指定 --docker 则用 Docker，否则默认本地
    # 如果显式指定 --local 也用本地模式
    local_mode = not args.docker or args.local
    
    try:
        results, summary = run_test_suite(
            config_path=args.config,
            project_filter=args.project,
            difficulty_filter=args.difficulty,
            skip_setup=args.skip_setup,
            local_mode=local_mode
        )
        
        # 设置退出码
        success_rate = summary.get("success_rate", 0)
        if success_rate >= 80:
            sys.exit(0)  # 成功
        else:
            sys.exit(1)  # 失败（成功率低于80%）
            
    except KeyboardInterrupt:
        logger.info("\n⚠️  测试被用户中断")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ 测试套件执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

