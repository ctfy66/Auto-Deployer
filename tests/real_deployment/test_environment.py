"""Docker测试环境管理 - 创建和管理用于测试的Docker容器"""
import time
import socket
import logging
from typing import Dict, Optional, Any
from contextlib import contextmanager

try:
    import docker
except ImportError:
    docker = None  # docker库未安装时设为None

logger = logging.getLogger(__name__)


class TestEnvironment:
    """Docker测试环境管理器"""
    
    def __init__(
        self, 
        base_image: str = "ubuntu:22.04", 
        container_name: str = "autodep-test-env"
    ):
        """
        初始化测试环境管理器
        
        Args:
            base_image: Docker基础镜像
            container_name: 容器名称
        """
        self.client: Optional[docker.DockerClient] = None
        self.container: Optional[docker.models.containers.Container] = None
        self.base_image = base_image
        self.container_name = container_name
        self.ssh_port: Optional[int] = None
        self.ssh_credentials: Optional[Dict[str, str]] = None
    
    def setup(self) -> Dict[str, Any]:
        """
        创建并配置测试容器，返回SSH连接信息
        
        Returns:
            包含host, port, username, password的字典
        """
        if docker is None:
            raise ImportError(
                "docker库未安装。请运行: pip install docker"
            )
        
        try:
            # 1. 创建Docker客户端
            logger.info("🐳 连接Docker...")
            self.client = docker.from_env()
            self.client.ping()  # 测试连接
            
            # 2. 清理可能存在的旧容器
            self._cleanup_existing_container()
            
            # 3. 拉取基础镜像（如果不存在）
            logger.info(f"📦 检查基础镜像: {self.base_image}")
            try:
                self.client.images.get(self.base_image)
                logger.info("   镜像已存在")
            except docker.errors.ImageNotFound:
                logger.info("   拉取镜像中...")
                self.client.images.pull(self.base_image)
                logger.info("   镜像拉取完成")
            
            # 4. 创建并启动容器
            logger.info("🚀 创建测试容器...")
            self.container = self.client.containers.run(
                self.base_image,
                detach=True,
                tty=True,
                command="/bin/bash -c 'while true; do sleep 3600; done'",  # 保持容器运行
                name=self.container_name,
                remove=False,
                ports={},  # 稍后映射端口
            )
            
            # 等待容器启动
            time.sleep(2)
            self.container.reload()
            
            # 5. 配置国内镜像源（避免网络问题）
            logger.info("⚙️  配置软件源...")
            mirror_cmd = (
                "sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list && "
                "sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list"
            )
            result = self.container.exec_run(
                f'/bin/sh -c "{mirror_cmd}"',
                user="root",
                stdout=True,
                stderr=True
            )
            
            # 5. 安装SSH服务器
            logger.info("📦 安装SSH服务器...")
            install_cmd = (
                "apt-get update && "
                "DEBIAN_FRONTEND=noninteractive apt-get install -y openssh-server sudo && "
                "mkdir -p /var/run/sshd"
            )
            result = self.container.exec_run(
                f'/bin/sh -c "{install_cmd}"',
                user="root",
                stdout=True,
                stderr=True
            )
            if result.exit_code != 0:
                raise RuntimeError(f"SSH安装失败: {result.output.decode()}")
            
            # 6. 配置SSH
            logger.info("⚙️  配置SSH...")
            ssh_password = "testpass"
            ssh_config_cmd = (
                f"echo 'root:{ssh_password}' | chpasswd && "
                "sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && "
                "sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && "
                "/usr/sbin/sshd"
            )
            result = self.container.exec_run(
                f'/bin/sh -c "{ssh_config_cmd}"',
                user="root",
                stdout=True,
                stderr=True
            )
            if result.exit_code != 0:
                raise RuntimeError(f"SSH配置失败: {result.output.decode()}")
            
            # 7. 映射SSH端口
            self.ssh_port = self._find_free_port()
            self.container.reload()
            
            # 停止容器以重新配置端口映射
            self.container.stop()
            self.container.remove()
            
            # 重新创建容器并映射端口
            self.container = self.client.containers.run(
                self.base_image,
                detach=True,
                tty=True,
                command="/bin/bash -c 'while true; do sleep 3600; done'",
                name=self.container_name,
                remove=False,
                ports={22: self.ssh_port},
            )
            
            # 再次配置镜像源并安装SSH
            self.container.exec_run(f'/bin/sh -c "{mirror_cmd}"', user="root")
            self.container.exec_run(f'/bin/sh -c "{install_cmd}"', user="root")
            self.container.exec_run(f'/bin/sh -c "{ssh_config_cmd}"', user="root")
            
            # 8. 等待SSH服务就绪
            logger.info("⏳ 等待SSH服务就绪...")
            if not self._wait_for_ssh(max_wait=30):
                raise RuntimeError("SSH服务启动超时")
            
            # 9. 返回连接信息
            self.ssh_credentials = {
                "host": "localhost",
                "port": self.ssh_port,
                "username": "root",
                "password": ssh_password
            }
            
            logger.info(f"✅ 测试环境就绪")
            logger.info(f"   SSH地址: {self.ssh_credentials['username']}@{self.ssh_credentials['host']}:{self.ssh_credentials['port']}")
            
            return self.ssh_credentials
            
        except docker.errors.DockerException as e:
            logger.error(f"❌ Docker错误: {e}")
            raise RuntimeError(f"Docker操作失败: {e}")
        except Exception as e:
            logger.error(f"❌ 环境设置失败: {e}")
            self.cleanup()
            raise
    
    def cleanup(self) -> None:
        """停止并删除容器"""
        if self.container:
            try:
                logger.info("🧹 清理测试容器...")
                self.container.stop(timeout=5)
                self.container.remove()
                logger.info("   容器已删除")
            except docker.errors.NotFound:
                logger.debug("   容器不存在，跳过删除")
            except Exception as e:
                logger.warning(f"   清理容器时出错: {e}")
            finally:
                self.container = None
                self.ssh_port = None
                self.ssh_credentials = None
    
    def reset(self) -> Dict[str, Any]:
        """重置环境（清理后重新创建）"""
        self.cleanup()
        time.sleep(1)  # 等待容器完全删除
        return self.setup()
    
    def _cleanup_existing_container(self) -> None:
        """清理可能存在的同名容器"""
        try:
            existing = self.client.containers.get(self.container_name)
            logger.info(f"   发现已存在的容器，正在删除...")
            existing.stop(timeout=5)
            existing.remove()
            time.sleep(1)
        except docker.errors.NotFound:
            pass
        except Exception as e:
            logger.warning(f"   清理旧容器时出错: {e}")
    
    def _find_free_port(self) -> int:
        """查找空闲端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]
    
    def _wait_for_ssh(self, max_wait: int = 30) -> bool:
        """等待SSH服务就绪"""
        import socket
        
        if not self.ssh_port:
            return False
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', self.ssh_port))
                sock.close()
                if result == 0:
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False
    
    def __enter__(self):
        """上下文管理器入口"""
        return self.setup()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()

