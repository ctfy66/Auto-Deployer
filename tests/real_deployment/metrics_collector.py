"""指标收集器 - 收集和分析测试指标"""
import statistics
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional


@dataclass
class ProjectMetrics:
    """单个项目的测试指标"""
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
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


class MetricsCollector:
    """指标收集器"""
    
    @staticmethod
    def aggregate_metrics(results: List[ProjectMetrics]) -> Dict[str, Any]:
        """
        聚合所有项目的指标
        
        Args:
            results: 项目指标列表
            
        Returns:
            聚合后的指标字典
        """
        if not results:
            return {
                "total_projects": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0
            }
        
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0.0
        
        # 按难度分类
        by_difficulty = {}
        for r in results:
            diff = r.project_difficulty
            if diff not in by_difficulty:
                by_difficulty[diff] = {"total": 0, "success": 0}
            by_difficulty[diff]["total"] += 1
            if r.success:
                by_difficulty[diff]["success"] += 1
        
        # 计算各难度的成功率
        for diff in by_difficulty:
            stats = by_difficulty[diff]
            stats["success_rate"] = (
                stats["success"] / stats["total"] * 100 
                if stats["total"] > 0 else 0.0
            )
        
        # 只统计成功的项目
        successful_results = [r for r in results if r.success]
        
        # 计算平均指标
        avg_metrics = {}
        if successful_results:
            avg_metrics = {
                "deployment_time_seconds": statistics.mean(
                    [r.deployment_time_seconds for r in successful_results]
                ),
                "iterations": statistics.mean(
                    [r.total_iterations for r in successful_results]
                ),
                "commands": statistics.mean(
                    [r.total_commands for r in successful_results]
                ),
                "llm_calls": statistics.mean(
                    [r.llm_call_count for r in successful_results]
                ),
                "user_interactions": statistics.mean(
                    [r.user_interactions for r in successful_results]
                ),
                "error_recoveries": statistics.mean(
                    [r.error_recovery_count for r in successful_results]
                ),
            }
        else:
            avg_metrics = {
                "deployment_time_seconds": 0.0,
                "iterations": 0.0,
                "commands": 0.0,
                "llm_calls": 0.0,
                "user_interactions": 0.0,
                "error_recoveries": 0.0,
            }
        
        # 策略选择准确率
        strategy_results = [r for r in results if r.strategy_correct is not None]
        strategy_correct = sum(1 for r in strategy_results if r.strategy_correct)
        strategy_total = len(strategy_results)
        strategy_accuracy = (
            strategy_correct / strategy_total * 100 
            if strategy_total > 0 else 0.0
        )
        
        # 验证通过率
        verification_passed = sum(1 for r in results if r.verification_passed)
        verification_rate = (
            verification_passed / total * 100 
            if total > 0 else 0.0
        )
        
        return {
            "total_projects": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "by_difficulty": by_difficulty,
            "average_metrics": avg_metrics,
            "strategy_accuracy": strategy_accuracy,
            "verification_rate": verification_rate,
        }
    
    @staticmethod
    def calculate_statistics(metrics_list: List[ProjectMetrics]) -> Dict[str, Any]:
        """
        计算统计信息（平均值、中位数、最大值、最小值等）
        
        Args:
            metrics_list: 指标列表
            
        Returns:
            统计信息字典
        """
        if not metrics_list:
            return {}
        
        successful = [m for m in metrics_list if m.success]
        
        if not successful:
            return {
                "deployment_time": {"mean": 0, "median": 0, "min": 0, "max": 0},
                "iterations": {"mean": 0, "median": 0, "min": 0, "max": 0},
                "commands": {"mean": 0, "median": 0, "min": 0, "max": 0},
            }
        
        times = [m.deployment_time_seconds for m in successful]
        iterations = [m.total_iterations for m in successful]
        commands = [m.total_commands for m in successful]
        
        return {
            "deployment_time": {
                "mean": statistics.mean(times),
                "median": statistics.median(times),
                "min": min(times),
                "max": max(times),
            },
            "iterations": {
                "mean": statistics.mean(iterations),
                "median": statistics.median(iterations),
                "min": min(iterations),
                "max": max(iterations),
            },
            "commands": {
                "mean": statistics.mean(commands),
                "median": statistics.median(commands),
                "min": min(commands),
                "max": max(commands),
            },
        }
    
    @staticmethod
    def convert_dict_to_metrics(data: Dict[str, Any]) -> ProjectMetrics:
        """
        从字典转换为ProjectMetrics对象
        
        Args:
            data: 指标字典
            
        Returns:
            ProjectMetrics对象
        """
        return ProjectMetrics(
            project_name=data.get("project_name", ""),
            project_difficulty=data.get("project_difficulty", "unknown"),
            success=data.get("success", False),
            final_status=data.get("final_status", "unknown"),
            deployment_time_seconds=data.get("deployment_time_seconds", 0.0),
            total_iterations=data.get("total_iterations", 0),
            total_commands=data.get("total_commands", 0),
            llm_call_count=data.get("llm_call_count", 0),
            user_interactions=data.get("user_interactions", 0),
            error_recovery_count=data.get("error_recovery_count", 0),
            strategy_used=data.get("strategy_used", "unknown"),
            expected_strategy=data.get("expected_strategy", "unknown"),
            strategy_correct=data.get("strategy_correct"),
            verification_passed=data.get("verification_passed", False),
            verification_details=data.get("verification_details", []),
            log_file=data.get("log_file"),
            error=data.get("error"),
        )

