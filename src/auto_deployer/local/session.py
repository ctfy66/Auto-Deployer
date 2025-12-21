"""Local command execution session."""

from __future__ import annotations

import subprocess
import sys
import os
import platform
from dataclasses import dataclass
from typing import Optional


@dataclass
class LocalCommandResult:
    """Result of executing a local command."""
    command: str
    stdout: str
    stderr: str
    exit_status: int

    @property
    def ok(self) -> bool:
        return self.exit_status == 0


class LocalSession:
    """
    Local command execution session.
    
    Provides the same interface as SSHSession but executes commands locally.
    Supports Windows (PowerShell/cmd) and Unix (bash) systems.
    """

    def __init__(self, working_dir: Optional[str] = None) -> None:
        """
        Initialize local session.
        
        Args:
            working_dir: Working directory for commands. Defaults to home directory.
        """
        self.working_dir = working_dir or os.path.expanduser("~")
        self.is_windows = platform.system() == "Windows"
        self._connected = False

    def connect(self) -> None:
        """No-op for local session (for API compatibility with SSHSession)."""
        self._connected = True

    def close(self) -> None:
        """No-op for local session (for API compatibility with SSHSession)."""
        self._connected = False

    def __enter__(self) -> "LocalSession":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def run(
        self, 
        command: str, 
        *, 
        timeout: Optional[int] = None,
        idle_timeout: int = 60,
        stream_output: bool = True,
    ) -> LocalCommandResult:
        """
        Execute a command locally.
        
        Args:
            command: The command to execute
            timeout: Total timeout in seconds (default: 600 for stream mode)
            idle_timeout: Timeout for no output activity (default: 60 seconds)
            stream_output: Whether to stream output in real-time
            
        Returns:
            LocalCommandResult with stdout, stderr, and exit status
            
        Note:
            The idle_timeout helps detect commands that are waiting for input
            which would otherwise block forever.
        """
        # 设置默认总超时
        if timeout is None:
            timeout = 600  # 默认10分钟总超时
        
        # 转换命令格式（如果需要）
        actual_command = self._adapt_command(command)
        
        if stream_output:
            return self._run_streaming(actual_command, timeout, idle_timeout)
        else:
            return self._run_blocking(actual_command, timeout)

    def _adapt_command(self, command: str) -> str:
        """
        Adapt Linux-style commands to work on the current OS.
        
        For Windows, converts common Linux commands to PowerShell equivalents.
        """
        if not self.is_windows:
            return command
        
        # Windows 命令适配
        # 这里做一些基本的转换，复杂的交给 Agent 处理
        adaptations = {
            # 路径转换
            "~/": os.path.expanduser("~").replace("\\", "/") + "/",
            # 常用命令转换
            "rm -rf ": "Remove-Item -Recurse -Force ",
            "rm -r ": "Remove-Item -Recurse -Force ",
            "mkdir -p ": "New-Item -ItemType Directory -Force -Path ",
            "cat ": "Get-Content ",
            "ls ": "Get-ChildItem ",
            "pwd": "(Get-Location).Path",
            "which ": "Get-Command ",
            "export ": "$env:",  # export VAR=value -> $env:VAR=value
        }
        
        result = command
        for linux_cmd, win_cmd in adaptations.items():
            result = result.replace(linux_cmd, win_cmd)
        
        # 处理 source 命令（Windows 不需要）
        if result.startswith("source "):
            result = "# " + result  # 注释掉
        
        return result

    def _run_blocking(self, command: str, timeout: Optional[int]) -> LocalCommandResult:
        """Run command and wait for completion."""
        try:
            # 选择 shell
            if self.is_windows:
                # 使用 PowerShell
                result = subprocess.run(
                    ["powershell", "-Command", command],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.working_dir,
                    env=self._get_env(),
                )
            else:
                # 使用 bash
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=self.working_dir,
                    env=self._get_env(),
                    executable="/bin/bash",
                )
            
            return LocalCommandResult(
                command=command,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                exit_status=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return LocalCommandResult(
                command=command,
                stdout="",
                stderr=f"Command timed out after {timeout} seconds",
                exit_status=-1,
            )
        except Exception as e:
            return LocalCommandResult(
                command=command,
                stdout="",
                stderr=str(e),
                exit_status=-1,
            )

    def _run_streaming(self, command: str, timeout: int, idle_timeout: int) -> LocalCommandResult:
        """Run command with real-time output streaming and dual timeout mechanism."""
        import time
        import selectors
        import threading
        
        try:
            # 选择 shell
            if self.is_windows:
                process = subprocess.Popen(
                    ["powershell", "-Command", command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=self.working_dir,
                    env=self._get_env(),
                )
            else:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=self.working_dir,
                    env=self._get_env(),
                    executable="/bin/bash",
                )
            
            stdout_chunks = []
            stderr_chunks = []
            
            # 时间追踪
            start_time = time.time()
            last_activity_time = time.time()
            
            # Windows 不支持 selectors 用于 pipes，使用线程
            if self.is_windows:
                # 标志位：用于线程通信
                output_lock = threading.Lock()
                has_new_output = [False]  # 使用列表来允许在闭包中修改
                
                def read_stdout():
                    try:
                        for line in process.stdout:
                            with output_lock:
                                stdout_chunks.append(line)
                                has_new_output[0] = True
                            sys.stdout.write(line)
                            sys.stdout.flush()
                    except:
                        pass
                
                def read_stderr():
                    try:
                        for line in process.stderr:
                            with output_lock:
                                stderr_chunks.append(line)
                                has_new_output[0] = True
                            sys.stderr.write(line)
                            sys.stderr.flush()
                    except:
                        pass
                
                t1 = threading.Thread(target=read_stdout, daemon=True)
                t2 = threading.Thread(target=read_stderr, daemon=True)
                t1.start()
                t2.start()
                
                # 循环检查进程状态和超时
                while process.poll() is None:
                    # 检查是否有新输出
                    with output_lock:
                        if has_new_output[0]:
                            last_activity_time = time.time()
                            has_new_output[0] = False
                    
                    # 检查空闲超时
                    idle_time = time.time() - last_activity_time
                    if idle_time > idle_timeout:
                        process.kill()
                        t1.join(timeout=1)
                        t2.join(timeout=1)
                        return LocalCommandResult(
                            command=command,
                            stdout="".join(stdout_chunks).strip(),
                            stderr=f"IDLE_TIMEOUT: No output for {idle_timeout} seconds. "
                                   f"Possible causes:\n"
                                   f"1. Command waiting for input (interactive prompts) - use non-interactive alternatives\n"
                                   f"2. Long-running operation with no output - use progressive sleep checks (see Progressive Timeout Strategy)",
                            exit_status=-1,
                        )
                    
                    # 检查总超时
                    total_time = time.time() - start_time
                    if total_time > timeout:
                        process.kill()
                        t1.join(timeout=1)
                        t2.join(timeout=1)
                        return LocalCommandResult(
                            command=command,
                            stdout="".join(stdout_chunks).strip(),
                            stderr=f"TOTAL_TIMEOUT: Command exceeded {timeout} seconds total execution time. "
                                   f"For long-running operations, use progressive sleep checks instead of blocking commands (see Progressive Timeout Strategy).",
                            exit_status=-2,
                        )
                    
                    # 短暂休眠避免 CPU 占用过高
                    time.sleep(0.1)
                
                # 等待线程完成读取剩余输出
                t1.join(timeout=2)
                t2.join(timeout=2)
                
            else:
                # Unix: 使用 selectors
                sel = selectors.DefaultSelector()
                sel.register(process.stdout, selectors.EVENT_READ)
                sel.register(process.stderr, selectors.EVENT_READ)
                
                while process.poll() is None:
                    has_activity = False
                    
                    # 使用 select 读取可用输出
                    for key, _ in sel.select(timeout=0.1):
                        line = key.fileobj.readline()
                        if line:
                            if key.fileobj == process.stdout:
                                stdout_chunks.append(line)
                                sys.stdout.write(line)
                                sys.stdout.flush()
                            else:
                                stderr_chunks.append(line)
                                sys.stderr.write(line)
                                sys.stderr.flush()
                            has_activity = True
                    
                    # 如果有输出活动，重置空闲计时器
                    if has_activity:
                        last_activity_time = time.time()
                    
                    # 检查空闲超时
                    idle_time = time.time() - last_activity_time
                    if idle_time > idle_timeout:
                        process.kill()
                        sel.close()
                        return LocalCommandResult(
                            command=command,
                            stdout="".join(stdout_chunks).strip(),
                            stderr=f"IDLE_TIMEOUT: No output for {idle_timeout} seconds. "
                                   f"Possible causes:\n"
                                   f"1. Command waiting for input (interactive prompts) - use non-interactive alternatives\n"
                                   f"2. Long-running operation with no output - use progressive sleep checks (see Progressive Timeout Strategy)",
                            exit_status=-1,
                        )
                    
                    # 检查总超时
                    total_time = time.time() - start_time
                    if total_time > timeout:
                        process.kill()
                        sel.close()
                        return LocalCommandResult(
                            command=command,
                            stdout="".join(stdout_chunks).strip(),
                            stderr=f"TOTAL_TIMEOUT: Command exceeded {timeout} seconds total execution time. "
                                   f"For long-running operations, use progressive sleep checks instead of blocking commands (see Progressive Timeout Strategy).",
                            exit_status=-2,
                        )
                
                # 读取剩余输出
                for line in process.stdout:
                    stdout_chunks.append(line)
                    sys.stdout.write(line)
                    sys.stdout.flush()
                for line in process.stderr:
                    stderr_chunks.append(line)
                    sys.stderr.write(line)
                    sys.stderr.flush()
                
                sel.close()
            
            return LocalCommandResult(
                command=command,
                stdout="".join(stdout_chunks).strip(),
                stderr="".join(stderr_chunks).strip(),
                exit_status=process.returncode or 0,
            )
            
        except Exception as e:
            # 确保进程被终止
            try:
                process.kill()
            except:
                pass
            return LocalCommandResult(
                command=command,
                stdout="",
                stderr=str(e),
                exit_status=-1,
            )

    def _get_env(self) -> dict:
        """Get environment variables for subprocess."""
        env = os.environ.copy()
        
        # 确保常用工具在 PATH 中
        if self.is_windows:
            # Windows: 添加常用路径
            extra_paths = [
                os.path.expanduser("~\\AppData\\Roaming\\npm"),
                os.path.expanduser("~\\AppData\\Local\\Programs\\Python\\Python3*"),
                "C:\\Program Files\\Git\\bin",
                "C:\\Program Files\\nodejs",
            ]
        else:
            # Unix: 添加常用路径
            extra_paths = [
                os.path.expanduser("~/.nvm/versions/node/*/bin"),
                os.path.expanduser("~/.local/bin"),
                "/usr/local/bin",
            ]
        
        # 简单地添加到 PATH（实际的 glob 展开留给 shell）
        current_path = env.get("PATH", "")
        for p in extra_paths:
            if "*" not in p and os.path.exists(p):
                current_path = p + os.pathsep + current_path
        env["PATH"] = current_path
        
        return env
