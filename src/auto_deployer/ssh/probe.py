"""Remote host probing utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .session import SSHSession


@dataclass
class RemoteHostFacts:
    hostname: str
    kernel: str
    architecture: str
    os_release: str
    shell: str
    is_container: bool = False  # 是否在容器中运行
    has_systemd: bool = False   # 是否使用 systemd

    def to_payload(self) -> dict:
        return {
            "hostname": self.hostname,
            "kernel": self.kernel,
            "architecture": self.architecture,
            "os_release": self.os_release,
            "shell": self.shell,
            "is_container": self.is_container,
            "has_systemd": self.has_systemd,
        }


class RemoteProbe:
    """Collects remote host facts by running simple commands."""

    def collect(self, session: SSHSession) -> RemoteHostFacts:
        hostname = self._safe_run(session, "hostname")
        kernel = self._safe_run(session, "uname -sr")
        architecture = self._safe_run(session, "uname -m")
        os_release = self._safe_run(
            session,
            "lsb_release -ds || cat /etc/os-release || uname -sr",
        )
        shell = self._safe_run(session, "echo $SHELL")
        
        # 检测容器环境
        is_container = self._detect_container(session)
        has_systemd = self._detect_systemd(session)
        
        return RemoteHostFacts(
            hostname=hostname or "unknown",
            kernel=kernel or "unknown",
            architecture=architecture or "unknown",
            os_release=os_release or "unknown",
            shell=shell or "unknown",
            is_container=is_container,
            has_systemd=has_systemd,
        )

    def _safe_run(self, session: SSHSession, command: str) -> str:
        result = session.run(command)
        return result.stdout or result.stderr
    
    def _detect_container(self, session: SSHSession) -> bool:
        """检测远程主机是否在容器中运行"""
        try:
            # 方法 1: 检查 /.dockerenv
            result = session.run("test -f /.dockerenv && echo 'yes' || echo 'no'")
            if result.stdout and "yes" in result.stdout.lower():
                return True
            
            # 方法 2: 检查 /proc/1/cgroup
            result = session.run("cat /proc/1/cgroup 2>/dev/null | grep -E 'docker|containerd|lxc' && echo 'yes' || echo 'no'")
            if result.stdout and "yes" in result.stdout.lower():
                return True
            
            return False
        except Exception:
            return False
    
    def _detect_systemd(self, session: SSHSession) -> bool:
        """检测远程主机是否使用 systemd"""
        try:
            # 检查 PID 1 是否是 systemd
            result = session.run("cat /proc/1/comm 2>/dev/null")
            if result.stdout and "systemd" in result.stdout.strip():
                return True
            return False
        except Exception:
            return False
