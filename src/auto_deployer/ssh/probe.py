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

    def to_payload(self) -> dict:
        return {
            "hostname": self.hostname,
            "kernel": self.kernel,
            "architecture": self.architecture,
            "os_release": self.os_release,
            "shell": self.shell,
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
        return RemoteHostFacts(
            hostname=hostname or "unknown",
            kernel=kernel or "unknown",
            architecture=architecture or "unknown",
            os_release=os_release or "unknown",
            shell=shell or "unknown",
        )

    def _safe_run(self, session: SSHSession, command: str) -> str:
        result = session.run(command)
        return result.stdout or result.stderr
