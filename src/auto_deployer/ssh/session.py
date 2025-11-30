"""SSH session management built on Paramiko."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import paramiko

from .credentials import SSHCredentials


class SSHConnectionError(RuntimeError):
    """Raised when an SSH connection cannot be established."""

    pass


@dataclass
class SSHCommandResult:
    command: str
    stdout: str
    stderr: str
    exit_status: int

    @property
    def ok(self) -> bool:
        return self.exit_status == 0


class SSHSession:
    """High-level wrapper around paramiko.SSHClient."""

    def __init__(
        self,
        credentials: SSHCredentials,
        *,
        client_factory: Callable[[], paramiko.SSHClient] | None = None,
    ) -> None:
        self.credentials = credentials
        self._client_factory = client_factory or paramiko.SSHClient
        self._client: Optional[paramiko.SSHClient] = None

    @property
    def sudo_password(self) -> Optional[str]:
        """Return the password for sudo commands (same as SSH password)."""
        return self.credentials.password

    def __enter__(self) -> "SSHSession":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.close()

    def connect(self) -> None:
        if self._client:
            return
        client = self._client_factory()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            connect_kwargs = {
                "hostname": self.credentials.host,
                "port": self.credentials.port,
                "username": self.credentials.username,
                "timeout": self.credentials.timeout,
                "look_for_keys": False,
                "allow_agent": False,
            }
            if self.credentials.auth_method == "password":
                connect_kwargs["password"] = self.credentials.password
            else:
                connect_kwargs["key_filename"] = self.credentials.key_path
                if self.credentials.passphrase:
                    connect_kwargs["passphrase"] = self.credentials.passphrase
            client.connect(**connect_kwargs)
        except Exception as exc:  # pragma: no cover - network errors hard to simulate
            client.close()
            raise SSHConnectionError(str(exc)) from exc
        self._client = client

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def run(self, command: str, *, timeout: Optional[int] = None) -> SSHCommandResult:
        if not self._client:
            self.connect()
        assert self._client is not None
        
        # 自动处理 sudo 命令：使用 -S 选项通过 stdin 传递密码
        actual_command = command
        needs_sudo_password = command.strip().startswith("sudo ") and self.sudo_password
        if needs_sudo_password:
            # 确保 sudo 使用 -S 选项从 stdin 读取密码
            if "sudo -S" not in command:
                actual_command = command.replace("sudo ", "sudo -S ", 1)
        
        stdin, stdout, stderr = self._client.exec_command(actual_command, timeout=timeout)
        
        # 如果是 sudo 命令，通过 stdin 发送密码
        if needs_sudo_password and self.sudo_password:
            stdin.write(self.sudo_password + "\n")
            stdin.flush()
        
        exit_status = stdout.channel.recv_exit_status()
        stdout_text = stdout.read().decode("utf-8", errors="replace")
        stderr_text = stderr.read().decode("utf-8", errors="replace")
        return SSHCommandResult(
            command=command,
            stdout=stdout_text.strip(),
            stderr=stderr_text.strip(),
            exit_status=exit_status,
        )
