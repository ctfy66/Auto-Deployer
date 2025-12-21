"""本地测试环境管理 - 在本地机器上直接运行测试，无需 Docker 容器"""
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from auto_deployer.local import LocalProbe, LocalHostFacts

logger = logging.getLogger(__name__)


class LocalTestEnvironment:
    """本地测试环境管理器
    
    使用本地机器作为测试环境，避免 Docker in Docker 问题。
    适合测试需要 Docker 的项目以及其他所有类型的部署。
    """
    
    def __init__(
        self, 
        workspace_dir: str = "tests/results/local_workspace",
        cleanup_on_success: bool = False,
        cleanup_on_failure: bool = False
    ):
        """
        初始化本地测试环境管理器
        
        Args:
            workspace_dir: 测试工作空间目录
            cleanup_on_success: 成功后是否清理
            cleanup_on_failure: 失败后是否清理
        """
        self.workspace_dir = Path(workspace_dir)
        self.cleanup_on_success = cleanup_on_success
        self.cleanup_on_failure = cleanup_on_failure
        self.system_info: Optional[Dict[str, Any]] = None
        
    def setup(self) -> Dict[str, Any]:
        """
        设置本地测试环境
        
        Returns:
            包含测试环境配置的字典
        """
        logger.info("🏠 设置本地测试环境...")
        
        try:
            # 1. 创建工作空间目录
            self.workspace_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"   工作空间: {self.workspace_dir.absolute()}")
            
            # 2. 收集本地系统信息
            logger.info("🖥️  收集本地系统信息...")
            probe = LocalProbe()
            host_facts = probe.collect()
            
            logger.info(f"   系统: {host_facts.hostname} ({host_facts.os_release})")
            
            # 列出可用工具
            tools = []
            if host_facts.has_git:
                tools.append("git")
            if host_facts.has_node:
                tools.append("node")
            if host_facts.has_python3:
                tools.append("python")
            if host_facts.has_docker:
                tools.append("docker")
            
            if tools:
                logger.info(f"   可用工具: {', '.join(tools)}")
            else:
                logger.warning("   ⚠️  未检测到常用开发工具")
            
            # 3. 准备配置信息
            self.system_info = host_facts.to_payload()
            
            config = {
                "mode": "local",
                "workspace": str(self.workspace_dir.absolute()),
                "system_info": self.system_info
            }
            
            logger.info("✅ 本地测试环境就绪")
            
            return config
            
        except Exception as e:
            logger.error(f"❌ 本地环境设置失败: {e}")
            raise
    
    def cleanup(self) -> None:
        """清理测试工作空间"""
        if self.workspace_dir.exists():
            try:
                logger.info("🧹 清理测试工作空间...")
                shutil.rmtree(self.workspace_dir)
                logger.info("   工作空间已清理")
            except Exception as e:
                logger.warning(f"   清理工作空间时出错: {e}")
    
    def reset(self) -> Dict[str, Any]:
        """重置环境（清理后重新设置）"""
        self.cleanup()
        return self.setup()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self.setup()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        # 根据配置决定是否清理
        should_cleanup = False
        
        if exc_type is None:
            # 没有异常，成功完成
            should_cleanup = self.cleanup_on_success
        else:
            # 有异常，失败
            should_cleanup = self.cleanup_on_failure
        
        if should_cleanup:
            self.cleanup()
