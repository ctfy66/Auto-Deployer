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
    
    # 可用工具
    has_git: bool = False
    has_node: bool = False
    has_npm: bool = False
    has_python3: bool = False
    has_pip: bool = False
    has_docker: bool = False
    
    def to_payload(self) -> dict:
        """Convert to dict for LLM context."""
        return {
            "hostname": self.hostname,
            "os_name": self.os_name,
            "os_release": self.os_release,
            "kernel": self.kernel,
            "architecture": self.architecture,
            "python_version": self.python_version,
            "home_dir": self.home_dir,
            "available_tools": {
                "git": self.has_git,
                "node": self.has_node,
                "npm": self.has_npm,
                "python3": self.has_python3,
                "pip": self.has_pip,
                "docker": self.has_docker,
            },
        }


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
