"""真实部署测试执行器 - 执行真实部署测试并收集指标"""
import time
import json
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

from auto_deployer.workflow import DeploymentWorkflow, DeploymentRequest, LocalDeploymentRequest
from auto_deployer.config import AppConfig
from .test_projects import TestProject
from .test_environment import TestEnvironment

logger = logging.getLogger(__name__)


class DeploymentTester:
    """真实部署测试执行器"""
    
    def __init__(self, config: AppConfig, log_dir: Path = Path("tests/results")):
        """
        初始化测试器
        
        Args:
            config: Auto-Deployer应用配置
            log_dir: 日志和结果保存目录
        """
        self.config = config
        self.log_dir = Path(log_dir)
        self.workspace_dir = self.log_dir / "workspace"
        self.logs_dir = self.log_dir / "logs"
        
        # 创建目录
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    def test_project(
        self, 
        project: TestProject, 
        env_config: Dict[str, Any],
        timeout_minutes: int = 30,
        local_mode: bool = False
    ) -> Dict[str, Any]:
        """
        测试单个项目部署
        
        Args:
            project: 测试项目配置
            env_config: 环境配置（SSH连接信息或本地环境信息）
            timeout_minutes: 超时时间（分钟）
            local_mode: 是否使用本地模式（True=本地，False=SSH远程）
            
        Returns:
            包含所有指标的字典
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🧪 测试项目: {project.name}")
        logger.info(f"   仓库: {project.repo_url}")
        logger.info(f"   难度: {project.difficulty}")
        logger.info(f"   预期策略: {project.expected_strategy}")
        logger.info(f"   测试模式: {'🏠 本地' if local_mode else '🐳 Docker容器'}")
        logger.info(f"{'='*60}\n")
        
        start_time = time.time()
        
        # 创建部署工作流
        workflow = DeploymentWorkflow(
            config=self.config,
            workspace=str(self.workspace_dir)
        )
        
        try:
            # 根据模式创建不同的部署请求
            if local_mode:
                # 本地模式
                request = LocalDeploymentRequest(
                    repo_url=project.repo_url,
                    deploy_dir=None  # 使用默认目录
                )
                logger.info("🚀 开始本地部署...")
                workflow.run_local_deploy(request)
            else:
                # SSH 远程模式（Docker 容器）
                request = DeploymentRequest(
                    repo_url=project.repo_url,
                    host=env_config["host"],
                    port=env_config["port"],
                    username=env_config["username"],
                    auth_method="password",
                    password=env_config["password"],
                    key_path=None,
                    deploy_dir=None
                )
                logger.info("🚀 开始远程部署...")
                workflow.run_deploy(request)
            
            # 等待部署完成（Agent会自己完成）
            deployment_time = time.time() - start_time
            
            # 查找最新的日志文件
            log_file = self._find_latest_log(project.name)
            
            if not log_file:
                logger.warning("⚠️  未找到部署日志文件")
                return {
                    "project_name": project.name,
                    "project_difficulty": project.difficulty,
                    "success": False,
                    "error": "Log file not found",
                    "deployment_time_seconds": deployment_time
                }
            
            # 解析日志获取指标
            metrics = self._extract_metrics(log_file, deployment_time, project)
            
            # 验证部署结果
            logger.info("🔍 验证部署结果...")
            verification_result = self._verify_deployment(project, env_config)
            
            metrics.update({
                "verification_passed": verification_result["passed"],
                "verification_details": verification_result["details"]
            })
            
            # 最终成功判断：部署成功且验证通过
            metrics["success"] = (
                metrics.get("success", False) and 
                verification_result["passed"]
            )
            
            logger.info(f"✅ 测试完成: {'成功' if metrics['success'] else '失败'}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ 测试失败: {e}", exc_info=True)
            return {
                "project_name": project.name,
                "project_difficulty": project.difficulty,
                "success": False,
                "error": str(e),
                "deployment_time_seconds": time.time() - start_time
            }
    
    def _find_latest_log(self, project_name: str) -> Optional[Path]:
        """
        查找项目的最新部署日志
        
        Args:
            project_name: 项目名称
            
        Returns:
            日志文件路径，如果未找到则返回None
        """
        # 查找agent_logs目录（Agent默认保存位置）
        agent_logs_dir = Path("agent_logs")
        if not agent_logs_dir.exists():
            # 尝试在logs目录查找
            agent_logs_dir = self.logs_dir
        
        # 查找匹配的日志文件
        pattern = f"deploy_{project_name}_*.json"
        log_files = list(agent_logs_dir.glob(pattern))
        
        if not log_files:
            # 尝试查找所有最近的日志文件
            all_logs = list(agent_logs_dir.glob("deploy_*.json"))
            if all_logs:
                # 返回最新的
                return max(all_logs, key=lambda p: p.stat().st_mtime)
            return None
        
        # 返回最新的匹配文件
        return max(log_files, key=lambda p: p.stat().st_mtime)
    
    def _extract_metrics(
        self, 
        log_file: Path, 
        deployment_time: float, 
        project: TestProject
    ) -> Dict[str, Any]:
        """
        从日志文件中提取指标
        
        Args:
            log_file: 日志文件路径
            deployment_time: 部署耗时（秒）
            project: 测试项目配置
            
        Returns:
            指标字典
        """
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception as e:
            logger.error(f"读取日志文件失败: {e}")
            return {
                "success": False,
                "error": f"Failed to read log: {e}",
                "deployment_time_seconds": deployment_time
            }
        
        # 提取步骤信息
        steps = log.get("steps", [])
        
        # 计算各种指标
        total_iterations = len(steps)
        total_commands = 0
        user_interactions = 0
        error_recovery_count = 0
        
        for step in steps:
            # 计算命令数
            if isinstance(step.get("result"), dict):
                commands = step.get("result", {}).get("commands", [])
                if isinstance(commands, list):
                    total_commands += len(commands)
                else:
                    total_commands += 1
            else:
                total_commands += 1
            
            # 统计用户交互
            if step.get("action") == "ask_user":
                user_interactions += 1
            
            # 统计错误恢复
            if isinstance(step.get("result"), dict):
                if not step.get("result", {}).get("success", True):
                    error_recovery_count += 1
        
        # 提取策略信息
        plan = log.get("plan", {})
        strategy_used = plan.get("strategy") if plan else None
        if not strategy_used:
            # 尝试从日志中推断策略
            commands_str = str(log).lower()
            if "docker-compose" in commands_str:
                strategy_used = "docker-compose"
            elif "docker" in commands_str:
                strategy_used = "docker"
            else:
                strategy_used = "traditional"
        
        strategy_correct = (
            strategy_used == project.expected_strategy
            if strategy_used and project.expected_strategy
            else None
        )
        
        # 构建指标字典
        metrics = {
            "project_name": project.name,
            "project_difficulty": project.difficulty,
            "success": log.get("status") == "success",
            "final_status": log.get("status", "unknown"),
            "deployment_time_seconds": deployment_time,
            
            # 效率指标
            "total_iterations": total_iterations,
            "total_commands": total_commands,
            
            # LLM相关
            "llm_call_count": total_iterations,  # 每次迭代一次LLM调用
            
            # 质量指标
            "user_interactions": user_interactions,
            "error_recovery_count": error_recovery_count,
            
            # 策略选择
            "strategy_used": strategy_used,
            "expected_strategy": project.expected_strategy,
            "strategy_correct": strategy_correct,
            
            # 日志文件
            "log_file": str(log_file),
        }
        
        return metrics
    
    def _verify_deployment(
        self, 
        project: TestProject, 
        env_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        验证部署结果
        
        Args:
            project: 测试项目配置
            env_config: 环境配置
            
        Returns:
            验证结果字典
        """
        verification = project.verification
        urls = verification.urls
        
        if not urls:
            return {
                "passed": True,
                "details": [{"message": "No verification URLs defined"}]
            }
        
        results = []
        all_passed = True
        
        for url in urls:
            try:
                # 发送HTTP请求
                response = requests.get(
                    url,
                    timeout=verification.timeout,
                    allow_redirects=True
                )
                
                expected_status = verification.expected_status
                status_match = response.status_code == expected_status
                
                # 检查内容（如果配置了）
                content_match = True
                if verification.expected_content:
                    content_match = verification.expected_content in response.text
                
                passed = status_match and content_match
                all_passed = all_passed and passed
                
                results.append({
                    "url": url,
                    "status_code": response.status_code,
                    "expected_status": expected_status,
                    "status_match": status_match,
                    "content_match": content_match,
                    "passed": passed,
                    "response_length": len(response.text)
                })
                
                logger.info(
                    f"   {url}: {response.status_code} "
                    f"({'✅' if passed else '❌'})"
                )
                
            except requests.exceptions.Timeout:
                results.append({
                    "url": url,
                    "error": "Timeout",
                    "passed": False
                })
                all_passed = False
                logger.warning(f"   {url}: 超时")
                
            except requests.exceptions.ConnectionError:
                results.append({
                    "url": url,
                    "error": "Connection refused",
                    "passed": False
                })
                all_passed = False
                logger.warning(f"   {url}: 连接被拒绝")
                
            except Exception as e:
                results.append({
                    "url": url,
                    "error": str(e),
                    "passed": False
                })
                all_passed = False
                logger.warning(f"   {url}: 错误 - {e}")
        
        return {
            "passed": all_passed,
            "details": results
        }

