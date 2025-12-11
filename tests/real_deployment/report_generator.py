"""测试报告生成器 - 生成JSON和Markdown格式的测试报告"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from .metrics_collector import ProjectMetrics


class ReportGenerator:
    """测试报告生成器"""
    
    def __init__(self, output_dir: Path = Path("tests/results/reports")):
        """
        初始化报告生成器
        
        Args:
            output_dir: 报告输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_json_report(
        self, 
        results: List[ProjectMetrics], 
        summary: Dict[str, Any],
        config: Dict[str, Any]
    ) -> Path:
        """
        生成JSON格式报告
        
        Args:
            results: 项目指标列表
            summary: 聚合摘要
            config: 测试配置
            
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"test_report_{timestamp}.json"
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "config": config,
            "summary": summary,
            "results": [r.to_dict() for r in results]
        }
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        return report_file
    
    def generate_markdown_report(
        self, 
        results: List[ProjectMetrics], 
        summary: Dict[str, Any]
    ) -> Path:
        """
        生成Markdown格式报告
        
        Args:
            results: 项目指标列表
            summary: 聚合摘要
            
        Returns:
            报告文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.output_dir / f"test_report_{timestamp}.md"
        
        lines = []
        
        # 标题
        lines.append("# Auto-Deployer 真实部署测试报告")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # 摘要
        lines.append("## 📊 测试摘要")
        lines.append("")
        lines.append(f"- **总项目数**: {summary['total_projects']}")
        lines.append(f"- **成功**: {summary['successful']} ✅")
        lines.append(f"- **失败**: {summary['failed']} ❌")
        lines.append(f"- **成功率**: {summary['success_rate']:.1f}%")
        lines.append("")
        
        # 按难度分类
        if summary.get("by_difficulty"):
            lines.append("### 按难度分类")
            lines.append("")
            lines.append("| 难度 | 成功 | 总数 | 成功率 |")
            lines.append("|------|------|------|--------|")
            for diff, stats in summary["by_difficulty"].items():
                lines.append(
                    f"| {diff} | {stats['success']} | {stats['total']} | "
                    f"{stats['success_rate']:.1f}% |"
                )
            lines.append("")
        
        # 平均指标
        if summary.get("average_metrics"):
            lines.append("### 平均指标（仅成功项目）")
            lines.append("")
            avg = summary["average_metrics"]
            lines.append(f"- **部署时间**: {avg['deployment_time_seconds']:.1f}秒")
            lines.append(f"- **迭代次数**: {avg['iterations']:.1f}")
            lines.append(f"- **命令数**: {avg['commands']:.1f}")
            lines.append(f"- **LLM调用**: {avg['llm_calls']:.1f}")
            lines.append(f"- **用户交互**: {avg['user_interactions']:.1f}")
            lines.append(f"- **错误恢复**: {avg['error_recoveries']:.1f}")
            lines.append("")
        
        # 策略准确率
        if "strategy_accuracy" in summary:
            lines.append(f"### 策略选择准确率: {summary['strategy_accuracy']:.1f}%")
            lines.append("")
        
        # 验证通过率
        if "verification_rate" in summary:
            lines.append(f"### 部署验证通过率: {summary['verification_rate']:.1f}%")
            lines.append("")
        
        # 详细结果
        lines.append("## 📋 详细结果")
        lines.append("")
        
        for result in results:
            status_emoji = "✅" if result.success else "❌"
            lines.append(f"### {status_emoji} {result.project_name}")
            lines.append("")
            lines.append(f"- **难度**: {result.project_difficulty}")
            lines.append(f"- **状态**: {result.final_status}")
            lines.append(f"- **部署时间**: {result.deployment_time_seconds:.1f}秒")
            lines.append(f"- **迭代次数**: {result.total_iterations}")
            lines.append(f"- **命令数**: {result.total_commands}")
            lines.append(f"- **策略**: {result.strategy_used} (期望: {result.expected_strategy})")
            
            if result.strategy_correct is not None:
                strategy_emoji = "✅" if result.strategy_correct else "❌"
                lines.append(f"- **策略正确**: {strategy_emoji}")
            
            lines.append(f"- **验证通过**: {'✅' if result.verification_passed else '❌'}")
            
            if result.user_interactions > 0:
                lines.append(f"- **用户交互**: {result.user_interactions}次")
            
            if result.error_recovery_count > 0:
                lines.append(f"- **错误恢复**: {result.error_recovery_count}次")
            
            if result.error:
                lines.append(f"- **错误**: {result.error}")
            
            if result.log_file:
                lines.append(f"- **日志文件**: `{result.log_file}`")
            
            lines.append("")
        
        # 写入文件
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return report_file
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """
        在控制台打印摘要
        
        Args:
            summary: 聚合摘要
        """
        print(f"\n{'='*60}")
        print("📊 测试报告")
        print(f"{'='*60}")
        print(f"总项目数: {summary['total_projects']}")
        print(f"成功: {summary['successful']} ✅")
        print(f"失败: {summary['failed']} ❌")
        print(f"成功率: {summary['success_rate']:.1f}%")
        print()
        
        # 按难度分类
        if summary.get("by_difficulty"):
            print("按难度分类:")
            for diff, stats in summary["by_difficulty"].items():
                print(
                    f"  {diff}: {stats['success']}/{stats['total']} "
                    f"({stats['success_rate']:.1f}%)"
                )
            print()
        
        # 平均指标
        if summary.get("average_metrics"):
            print("平均指标（仅成功项目）:")
            avg = summary["average_metrics"]
            print(f"  部署时间: {avg['deployment_time_seconds']:.1f}秒")
            print(f"  迭代次数: {avg['iterations']:.1f}")
            print(f"  命令数: {avg['commands']:.1f}")
            print(f"  LLM调用: {avg['llm_calls']:.1f}")
            if avg.get('user_interactions', 0) > 0:
                print(f"  用户交互: {avg['user_interactions']:.1f}")
            if avg.get('error_recoveries', 0) > 0:
                print(f"  错误恢复: {avg['error_recoveries']:.1f}")
            print()
        
        # 策略准确率
        if "strategy_accuracy" in summary:
            print(f"策略选择准确率: {summary['strategy_accuracy']:.1f}%")
            print()
        
        # 验证通过率
        if "verification_rate" in summary:
            print(f"部署验证通过率: {summary['verification_rate']:.1f}%")
            print()
        
        print(f"{'='*60}\n")

