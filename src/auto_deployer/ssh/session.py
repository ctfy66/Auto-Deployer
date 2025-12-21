"""SSH session management built on Paramiko."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import paramiko
import socket

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

    def run(
        self,
        command: str,
        *,
        timeout: Optional[int] = None,
        idle_timeout: int = 60,
        stream_output: bool = True,
    ) -> SSHCommandResult:
        """
        Execute a command on the remote server.
        
        Args:
            command: The command to execute
            timeout: Total timeout in seconds (default: 600 for stream mode)
            idle_timeout: Timeout for no output activity (default: 60 seconds)
            stream_output: Whether to stream output in real-time
            
        Returns:
            SSHCommandResult with command output and exit status
            
        Note:
            The idle_timeout helps detect commands that are waiting for input
            (like newgrp, su -, passwd) which would otherwise block forever.
        """
        if not self._client:
            self.connect()
        assert self._client is not None
        
        import time
        import re
        
        # 设置默认总超时
        if timeout is None:
            timeout = 600  # 默认10分钟总超时
        
        # 预处理命令：加载常用环境（nvm 等）
        # 这样 node/npm 命令可以正常工作
        env_prefix = "source ~/.nvm/nvm.sh 2>/dev/null; source ~/.bashrc 2>/dev/null; "
        
        # 自动处理所有 sudo 命令：使用 -S 选项通过 stdin 传递密码
        actual_command = command
        needs_sudo_password = "sudo " in command and self.sudo_password
        if needs_sudo_password:
            # 替换所有的 sudo 为 sudo -S（除非已经是 sudo -S）
            actual_command = re.sub(r'\bsudo\s+(?!-S)', 'sudo -S ', actual_command)
        
        # 添加环境前缀
        actual_command = env_prefix + actual_command
        
        stdin, stdout, stderr = self._client.exec_command(actual_command, timeout=timeout)
        
        # 如果有 sudo 命令，通过 stdin 发送密码
        if needs_sudo_password and self.sudo_password:
            stdin.write(self.sudo_password + "\n")
            stdin.flush()
        
        # 记录时间
        start_time = time.time()
        last_activity_time = time.time()
        
        # 实时输出模式：边执行边显示输出
        if stream_output:
            import sys
            stdout_chunks = []
            stderr_chunks = []
            
            # 设置非阻塞读取
            stdout.channel.setblocking(0)
            stderr.channel.setblocking(0)
            
            while not stdout.channel.exit_status_ready():
                has_activity = False
                
                # 读取 stdout
                while stdout.channel.recv_ready():
                    chunk = stdout.channel.recv(1024).decode("utf-8", errors="replace")
                    stdout_chunks.append(chunk)
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    has_activity = True
                
                # 读取 stderr
                while stderr.channel.recv_stderr_ready():
                    chunk = stderr.channel.recv_stderr(1024).decode("utf-8", errors="replace")
                    stderr_chunks.append(chunk)
                    sys.stderr.write(chunk)
                    sys.stderr.flush()
                    has_activity = True
                
                # 如果有输出活动，重置空闲计时器
                if has_activity:
                    last_activity_time = time.time()
                
                # 检查空闲超时（长时间无输出）
                idle_time = time.time() - last_activity_time
                if idle_time > idle_timeout:
                    stdout.channel.close()
                    return SSHCommandResult(
                        command=command,
                        stdout="".join(stdout_chunks).strip(),
                        stderr=f"IDLE_TIMEOUT: No output for {idle_timeout} seconds. "
                               f"Possible causes:\n"
                               f"1. Command waiting for input (interactive prompts like newgrp, su -, passwd) - use non-interactive alternatives\n"
                               f"2. Long-running operation with no output - use progressive sleep checks (see Progressive Timeout Strategy)",
                        exit_status=-1,
                    )
                
                # 检查总超时
                total_time = time.time() - start_time
                if total_time > timeout:
                    stdout.channel.close()
                    return SSHCommandResult(
                        command=command,
                        stdout="".join(stdout_chunks).strip(),
                        stderr=f"TOTAL_TIMEOUT: Command exceeded {timeout} seconds total execution time. "
                               f"For long-running operations, use progressive sleep checks instead of blocking commands (see Progressive Timeout Strategy).",
                        exit_status=-2,
                    )
                
                # 短暂休眠避免 CPU 占用过高
                time.sleep(0.1)
            
            # 读取剩余输出
            while stdout.channel.recv_ready():
                chunk = stdout.channel.recv(1024).decode("utf-8", errors="replace")
                stdout_chunks.append(chunk)
                sys.stdout.write(chunk)
                sys.stdout.flush()
            
            while stderr.channel.recv_stderr_ready():
                chunk = stderr.channel.recv_stderr(1024).decode("utf-8", errors="replace")
                stderr_chunks.append(chunk)
                sys.stderr.write(chunk)
                sys.stderr.flush()
            
            exit_status = stdout.channel.recv_exit_status()
            stdout_text = "".join(stdout_chunks)
            stderr_text = "".join(stderr_chunks)
        else:
            # 原有模式：等待命令完成后返回（带超时保护）
            stdout.channel.settimeout(float(timeout))
            try:
                exit_status = stdout.channel.recv_exit_status()
                stdout_text = stdout.read().decode("utf-8", errors="replace")
                stderr_text = stderr.read().decode("utf-8", errors="replace")
            except socket.timeout:
                stdout.channel.close()
                return SSHCommandResult(
                    command=command,
                    stdout="",
                    stderr=f"TIMEOUT: Command did not complete within {timeout} seconds.",
                    exit_status=-1,
                )
        
        return SSHCommandResult(
            command=command,
            stdout=stdout_text.strip(),
            stderr=stderr_text.strip(),
            exit_status=exit_status,
        )
