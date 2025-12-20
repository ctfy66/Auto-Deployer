"""Local system probe for collecting host information."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class LocalHostFacts:
    """Facts about the local host system."""

    hostname: str
    os_name: str  # Windows, Linux, Darwin (macOS)
    os_release: str  # e.g., "Windows 10", "Ubuntu 22.04", "macOS 14.0"
    kernel: str
    architecture: str
    python_version: str
    home_dir: str

    # 环境特征
    is_container: bool = False  # 是否在容器中运行
    has_systemd: bool = False   # 是否使用 systemd
    shell_type: str = ""  # PowerShell, CMD, Bash, etc.

    # 可用工具
    has_git: bool = False
    has_node: bool = False
    has_npm: bool = False
    has_python3: bool = False
    has_pip: bool = False
    has_docker: bool = False

    # Windows特定信息
    is_msys2: bool = False  # 是否在MSYS2环境中
    python_venv_path: str = ""  # 虚拟环境激活脚本路径 (Scripts/ 或 bin/)

    def to_payload(self) -> dict:
        """Convert to dict for LLM context."""
        payload = {
            "hostname": self.hostname,
            "os_name": self.os_name,
            "os_release": self.os_release,
            "kernel": self.kernel,
            "architecture": self.architecture,
            "python_version": self.python_version,
            "home_dir": self.home_dir,
            "is_container": self.is_container,
            "has_systemd": self.has_systemd,
            "shell_type": self.shell_type,
            "available_tools": {
                "git": self.has_git,
                "node": self.has_node,
                "npm": self.has_npm,
                "python3": self.has_python3,
                "pip": self.has_pip,
                "docker": self.has_docker,
            },
        }
        return payload

        

class LocalProbe:
    """Collects information about the local system."""
    
    def __init__(self) -> None:
        self.is_windows = platform.system() == "Windows"
    
    def collect(self) -> LocalHostFacts:
        """Collect local host facts."""
        return LocalHostFacts(
            hostname=platform.node(),
            os_name=platform.system(),
            os_release=self._get_os_release(),
            kernel=platform.release(),
            architecture=platform.machine(),
            python_version=platform.python_version(),
            home_dir=os.path.expanduser("~"),
            is_container=self._detect_container(),
            has_systemd=self._detect_systemd(),
            has_git=self._check_command("git", "--version"),
            has_node=self._check_command("node", "--version"),
            has_npm=self._check_command("npm", "--version"),
            has_python3=self._check_command("python3" if not self.is_windows else "python", "--version"),
            has_pip=self._check_command("pip3" if not self.is_windows else "pip", "--version"),
            has_docker=self._check_command("docker", "--version"),
        )
    
    def _get_os_release(self) -> str:
        """Get detailed OS release info."""
        system = platform.system()
        
        if system == "Windows":
            return f"Windows {platform.release()} ({platform.version()})"
        elif system == "Darwin":
            mac_ver = platform.mac_ver()[0]
            return f"macOS {mac_ver}"
        elif system == "Linux":
            # 尝试读取 /etc/os-release
            try:
                with open("/etc/os-release") as f:
                    lines = f.readlines()
                    info = {}
                    for line in lines:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            info[key] = value.strip('"')
                    return info.get("PRETTY_NAME", f"Linux {platform.release()}")
            except Exception:
                return f"Linux {platform.release()}"
        else:
            return platform.platform()
    
    def _check_command(self, *cmd: str) -> bool:
        """Check if a command is available."""
        try:
            if self.is_windows:
                # Windows: 使用 where 或直接运行
                result = subprocess.run(
                    ["where", cmd[0]],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    return True
                # 备选：直接尝试运行
                result = subprocess.run(
                    list(cmd),
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0
            else:
                # Unix: 使用 which
                result = subprocess.run(
                    ["which", cmd[0]],
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0
        except Exception:
            return False
    
    def _detect_container(self) -> bool:
        """检测是否在容器中运行"""
        if self.is_windows:
            return False
        
        try:
            # 方法 1: 检查 /.dockerenv 文件
            if os.path.exists("/.dockerenv"):
                return True
            
            # 方法 2: 检查 /proc/1/cgroup
            if os.path.exists("/proc/1/cgroup"):
                with open("/proc/1/cgroup") as f:
                    content = f.read()
                    if "docker" in content or "containerd" in content or "lxc" in content:
                        return True
            
            # 方法 3: 检查 /proc/1/mountinfo
            if os.path.exists("/proc/1/mountinfo"):
                with open("/proc/1/mountinfo") as f:
                    content = f.read()
                    if "/docker/" in content:
                        return True
            
            return False
        except Exception:
            return False
    
    def _detect_systemd(self) -> bool:
        """检测是否使用 systemd"""
        if self.is_windows:
            return False
        
        try:
            # 检查 PID 1 是否是 systemd
            if os.path.exists("/proc/1/comm"):
                with open("/proc/1/comm") as f:
                    init = f.read().strip()
                    return init == "systemd"
            return False
        except Exception:
            return False
