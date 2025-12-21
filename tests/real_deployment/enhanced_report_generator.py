"""增强的测试报告生成器 - 生成包含详细信息的测试报告"""
import json
import statistics
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .enhanced_metrics import EnhancedProjectMetrics, SystemInfo, LLMConfig


class EnhancedReportGenerator:
    """增强的测试报告生成器"""
    
    def __init__(self, output_dir: Path = Path("tests/results/reports")):
        """
        初始化报告生成器
        
        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_enhanced_json_report(
        self,
        results: List[EnhancedProjectMetrics],
        test_start_time: datetime,
        test_end_time: datetime,
        parallel_workers: int
    ) -> Path:
        """
        生成增强的JSON格式报告
        
        Args:
            results: 增强的项目指标列表
            test_start_time: 测试开始时间
            test_end_time: 测试结束时间
            parallel_workers: 并行worker数量
            
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"parallel_test_report_{timestamp}.json"
        
        # 构建报告数据
        report_data = {
            "report_metadata": self._build_report_metadata(
                test_start_time, test_end_time, parallel_workers
            ),
            "test_environment": self._build_environment_section(results),
            "summary": self._aggregate_enhanced_metrics(results),
            "projects": [r.to_dict() for r in results]
        }
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return report_file
    
    def generate_enhanced_markdown_report(
        self,
        results: List[EnhancedProjectMetrics],
        summary: Dict[str, Any],
        test_start_time: datetime,
        test_end_time: datetime
    ) -> Path:
        """
        生成增强的Markdown格式报告
        
        Args:
            results: 增强的项目指标列表
            summary: 聚合摘要
            test_start_time: 测试开始时间
            test_end_time: 测试结束时间
            
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"parallel_test_report_{timestamp}.md"
        
        lines = []
        
        # 标题
        lines.append("# Auto-Deployer 并行测试报告")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**测试时长**: {(test_end_time - test_start_time).total_seconds() / 60:.1f} 分钟")
        lines.append("")
        
        # 测试环境
        if results:
            lines.append("## 🖥️ 测试环境")
            lines.append("")
            
            first_result = results[0]
            if first_result.system_info:
                sys_info = first_result.system_info
                lines.append(f"- **操作系统**: {sys_info.os_name} {sys_info.os_version}")
                lines.append(f"- **Python版本**: {sys_info.python_version}")
                lines.append(f"- **主机名**: {sys_info.hostname}")
                lines.append(f"- **CPU核心数**: {sys_info.cpu_count}")
                lines.append(f"- **总内存**: {sys_info.memory_total_gb} GB")
                lines.append("")
            
            if first_result.llm_config:
                llm_cfg = first_result.llm_config
                lines.append("### LLM 配置")
                lines.append("")
                lines.append(f"- **提供商**: {llm_cfg.provider}")
                lines.append(f"- **模型**: {llm_cfg.model}")
                lines.append(f"- **温度**: {llm_cfg.temperature}")
                lines.append(f"- **最大迭代次数**: {llm_cfg.max_iterations}")
                lines.append(f"- **每步最大迭代**: {llm_cfg.max_iterations_per_step}")
                lines.append(f"- **启用规划**: {'是' if llm_cfg.enable_planning else '否'}")
                lines.append("")
        
        # 测试摘要
        lines.append("## 📊 测试摘要")
        lines.append("")
        lines.append(f"- **总项目数**: {summary['total_projects']}")
        lines.append(f"- **成功**: {summary['successful']} ✅")
        lines.append(f"- **失败**: {summary['failed']} ❌")
        lines.append(f"- **成功率**: {summary['success_rate']:.1f}%")
        
        if summary.get('total_retries', 0) > 0:
            lines.append(f"- **总重试次数**: {summary['total_retries']}")
        
        lines.append("")
        
        # 性能统计
        if summary.get('avg_metrics'):
            lines.append("### ⚡ 性能统计（仅成功项目）")
            lines.append("")
            avg = summary['avg_metrics']
            lines.append(f"- **平均部署时间**: {avg['deployment_time_seconds']:.1f} 秒")
            lines.append(f"- **平均迭代次数**: {avg['iterations']:.1f}")
            lines.append(f"- **平均命令数**: {avg['commands']:.1f}")
            lines.append(f"- **平均LLM调用**: {avg['llm_calls']:.1f}")
            lines.append("")
        
        # 按难度分类
        if summary.get("by_difficulty"):
            lines.append("### 📈 按难度分类")
            lines.append("")
            lines.append("| 难度 | 成功 | 总数 | 成功率 |")
            lines.append("|------|------|------|--------|")
            for diff in ["easy", "medium", "hard"]:
                if diff in summary["by_difficulty"]:
                    stats = summary["by_difficulty"][diff]
                    lines.append(
                        f"| {diff.capitalize()} | {stats['success']} | "
                        f"{stats['total']} | {stats['success_rate']:.1f}% |"
                    )
            lines.append("")
        
        # 按策略分类
        if summary.get("by_strategy"):
            lines.append("### 🎯 按策略分类")
            lines.append("")
            lines.append("| 策略 | 成功 | 总数 | 成功率 |")
            lines.append("|------|------|------|--------|")
            for strategy, stats in summary["by_strategy"].items():
                lines.append(
                    f"| {strategy} | {stats['success']} | "
                    f"{stats['total']} | {stats['success_rate']:.1f}% |"
                )
            lines.append("")
        
        # 详细项目结果
        lines.append("## 📋 详细测试结果")
        lines.append("")
        lines.append("| 项目 | 难度 | 状态 | 时间(s) | 迭代 | 重试 |")
        lines.append("|------|------|------|---------|------|------|")
        
        for result in results:
            status = "✅" if result.success else "❌"
            retry_text = ""
            if result.retry_info and result.retry_info.total_attempts > 1:
                retry_text = f"{result.retry_info.failed_attempts}次"
            else:
                retry_text = "-"
            
            lines.append(
                f"| {result.project_name} | {result.project_difficulty} | "
                f"{status} | {result.deployment_time_seconds:.1f} | "
                f"{result.total_iterations} | {retry_text} |"
            )
        
        lines.append("")
        
        # 失败项目详情
        failed_results = [r for r in results if not r.success]
        if failed_results:
            lines.append("## ❌ 失败项目详情")
            lines.append("")
            for result in failed_results:
                lines.append(f"### {result.project_name}")
                lines.append("")
                lines.append(f"- **仓库**: {result.repo_url}")
                lines.append(f"- **难度**: {result.project_difficulty}")
                lines.append(f"- **错误**: {result.error or '未知错误'}")
                if result.retry_info:
                    lines.append(f"- **尝试次数**: {result.retry_info.total_attempts}")
                    if result.retry_info.retry_reasons:
                        lines.append(f"- **重试原因**:")
                        for reason in result.retry_info.retry_reasons:
                            lines.append(f"  - {reason}")
                lines.append("")
        
        # 写入文件
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return report_file
    
    def print_enhanced_summary(
        self,
        summary: Dict[str, Any],
        system_info: Optional[SystemInfo] = None
    ):
        """
        打印增强的控制台摘要
        
        Args:
            summary: 聚合摘要
            system_info: 系统信息（可选）
        """
        print("\n" + "="*60)
        print("📊 测试摘要")
        print("="*60)
        
        if system_info:
            print(f"\n🖥️  系统环境:")
            print(f"   {system_info.os_name} {system_info.os_version}")
            print(f"   Python {system_info.python_version}")
            print(f"   {system_info.cpu_count} CPU核心, {system_info.memory_total_gb} GB内存")
        
        print(f"\n📈 测试结果:")
        print(f"   总项目数: {summary['total_projects']}")
        print(f"   成功: {summary['successful']} ✅")
        print(f"   失败: {summary['failed']} ❌")
        print(f"   成功率: {summary['success_rate']:.1f}%")
        
        if summary.get('total_retries', 0) > 0:
            print(f"   总重试次数: {summary['total_retries']}")
        
        if summary.get('avg_metrics'):
            avg = summary['avg_metrics']
            print(f"\n⚡ 性能统计（仅成功项目）:")
            print(f"   平均部署时间: {avg['deployment_time_seconds']:.1f} 秒")
            print(f"   平均迭代次数: {avg['iterations']:.1f}")
            print(f"   平均LLM调用: {avg['llm_calls']:.1f}")
        
        if summary.get('by_difficulty'):
            print(f"\n📊 按难度分类:")
            for diff in ["easy", "medium", "hard"]:
                if diff in summary["by_difficulty"]:
                    stats = summary["by_difficulty"][diff]
                    print(
                        f"   {diff.capitalize()}: {stats['success']}/{stats['total']} "
                        f"({stats['success_rate']:.1f}%)"
                    )
        
        print("="*60 + "\n")
    
    def _build_report_metadata(
        self,
        test_start_time: datetime,
        test_end_time: datetime,
        parallel_workers: int
    ) -> Dict[str, Any]:
        """构建报告元数据"""
        duration_minutes = (test_end_time - test_start_time).total_seconds() / 60
        
        return {
            "generated_at": datetime.now().isoformat(),
            "test_start_time": test_start_time.isoformat(),
            "test_end_time": test_end_time.isoformat(),
            "test_duration_minutes": round(duration_minutes, 2),
            "parallel_workers": parallel_workers
        }
    
    def _build_environment_section(
        self,
        results: List[EnhancedProjectMetrics]
    ) -> Dict[str, Any]:
        """构建环境信息部分"""
        if not results:
            return {}
        
        first_result = results[0]
        env_section = {}
        
        if first_result.system_info:
            env_section["system"] = first_result.system_info.to_dict()
        
        if first_result.llm_config:
            env_section["llm_config"] = first_result.llm_config.to_dict()
        
        return env_section
    
    def _aggregate_enhanced_metrics(
        self,
        results: List[EnhancedProjectMetrics]
    ) -> Dict[str, Any]:
        """聚合增强指标"""
        if not results:
            return {
                "total_projects": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
                "total_retries": 0
            }
        
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0.0
        
        # 统计重试次数
        total_retries = sum(
            r.retry_info.failed_attempts 
            for r in results 
            if r.retry_info
        )
        
        # 按难度分类
        by_difficulty = self._calculate_multi_dimension_stats(
            results, 
            lambda r: r.project_difficulty
        )
        
        # 按策略分类
        by_strategy = self._calculate_multi_dimension_stats(
            results,
            lambda r: r.strategy_used
        )
        
        # 计算平均指标（只统计成功的项目）
        successful_results = [r for r in results if r.success]
        avg_metrics = {}
        
        if successful_results:
            avg_metrics = {
                "deployment_time_seconds": round(
                    statistics.mean([r.deployment_time_seconds for r in successful_results]), 1
                ),
                "iterations": round(
                    statistics.mean([r.total_iterations for r in successful_results]), 1
                ),
                "commands": round(
                    statistics.mean([r.total_commands for r in successful_results]), 1
                ),
                "llm_calls": round(
                    statistics.mean([r.llm_call_count for r in successful_results]), 1
                ),
            }
        
        return {
            "total_projects": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(success_rate, 1),
            "total_retries": total_retries,
            "by_difficulty": by_difficulty,
            "by_strategy": by_strategy,
            "avg_metrics": avg_metrics
        }
    
    def _calculate_multi_dimension_stats(
        self,
        results: List[EnhancedProjectMetrics],
        key_func
    ) -> Dict[str, Dict[str, Any]]:
        """
        按指定维度计算统计信息
        
        Args:
            results: 结果列表
            key_func: 提取维度键的函数
            
        Returns:
            按维度分组的统计信息
        """
        stats = {}
        
        for result in results:
            key = key_func(result)
            if key not in stats:
                stats[key] = {"total": 0, "success": 0}
            
            stats[key]["total"] += 1
            if result.success:
                stats[key]["success"] += 1
        
        # 计算成功率
        for key in stats:
            total = stats[key]["total"]
            success = stats[key]["success"]
            stats[key]["success_rate"] = round(
                (success / total * 100) if total > 0 else 0.0, 
                1
            )
        
        return stats
