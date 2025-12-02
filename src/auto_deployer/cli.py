"""Command-line interface for Auto-Deployer."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import AppConfig, load_config
from .workflow import DeploymentRequest, DeploymentWorkflow


@dataclass
class CLIContext:
    """Context captured from CLI arguments."""

    config: AppConfig
    workspace: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="auto-deployer",
        description="Deploy a GitHub repository to a remote server via SSH.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a JSON config file overriding defaults.",
    )
    parser.add_argument(
        "--workspace",
        type=str,
        default=None,
        help="Directory for local repository analysis.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    deploy_parser = subparsers.add_parser(
        "deploy", help="Trigger a deployment for a GitHub repository"
    )
    deploy_parser.add_argument("--repo", required=True, help="Git repository URL")
    
    # 本地部署模式
    deploy_parser.add_argument(
        "--local", "-L", action="store_true",
        help="Deploy locally on this machine (no SSH needed)"
    )
    deploy_parser.add_argument(
        "--deploy-dir", type=str, default=None,
        help="Local directory for deployment (default: ~/app)"
    )
    
    # SSH 远程部署选项
    deploy_parser.add_argument("--host", help="Target server host (for remote deployment)")
    deploy_parser.add_argument("--port", type=int, default=None, help="SSH port")
    deploy_parser.add_argument("--user", help="SSH username")
    deploy_parser.add_argument(
        "--auth-method",
        choices=["password", "key"],
        help="SSH authentication method",
    )
    deploy_parser.add_argument("--password", help="SSH password", default=None)
    deploy_parser.add_argument(
        "--key-path", help="Path to SSH private key", default=None
    )

    # logs 子命令 - 查看 Agent 日志
    logs_parser = subparsers.add_parser(
        "logs", help="View agent deployment logs"
    )
    logs_parser.add_argument(
        "--list", "-l", action="store_true", dest="list_logs",
        help="List all available logs"
    )
    logs_parser.add_argument(
        "--latest", action="store_true",
        help="Show the latest deployment log"
    )
    logs_parser.add_argument(
        "--file", "-f", type=str,
        help="Show a specific log file"
    )
    logs_parser.add_argument(
        "--summary", "-s", action="store_true",
        help="Show summary only (not full output)"
    )

    return parser


def _build_context(args: argparse.Namespace) -> CLIContext:
    config = load_config(args.config)
    workspace = args.workspace or config.deployment.workspace_root
    return CLIContext(
        config=config,
        workspace=workspace,
    )


def handle_logs_command(args: argparse.Namespace) -> int:
    """Handle the logs subcommand."""
    log_dir = Path.cwd() / "agent_logs"
    
    if not log_dir.exists():
        print("📁 No agent logs found. Run a deployment first.")
        return 0
    
    log_files = sorted(log_dir.glob("deploy_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not log_files:
        print("📁 No deployment logs found.")
        return 0
    
    # 列出所有日志
    if args.list_logs:
        print(f"📁 Agent logs in: {log_dir}\n")
        print(f"{'#':<4} {'Status':<12} {'Repository':<30} {'Time':<20} {'File'}")
        print("-" * 100)
        for i, log_file in enumerate(log_files, 1):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                status = data.get("status", "unknown")
                repo = data.get("repo_url", "").split("/")[-1].replace(".git", "")
                start_time = data.get("start_time", "")[:19].replace("T", " ")
                status_emoji = {"success": "✅", "failed": "❌", "running": "🔄"}.get(status, "❓")
                print(f"{i:<4} {status_emoji} {status:<10} {repo:<30} {start_time:<20} {log_file.name}")
            except Exception:
                print(f"{i:<4} ❓ {'error':<10} {'?':<30} {'?':<20} {log_file.name}")
        return 0
    
    # 选择要显示的日志文件
    target_file = None
    if args.file:
        target_file = Path(args.file)
        if not target_file.exists():
            # 尝试在 log_dir 中查找
            target_file = log_dir / args.file
        if not target_file.exists():
            print(f"❌ Log file not found: {args.file}")
            return 1
    elif args.latest or not (args.list_logs or args.file):
        # 默认显示最新的
        target_file = log_files[0]
    
    if target_file:
        show_log_file(target_file, summary_only=args.summary)
    
    return 0


def show_log_file(log_file: Path, summary_only: bool = False) -> None:
    """Display a deployment log file."""
    with open(log_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    status = data.get("status", "unknown")
    status_emoji = {"success": "✅", "failed": "❌", "running": "🔄", "max_iterations": "⏱️"}.get(status, "❓")
    
    print(f"\n{'='*60}")
    print(f"📄 Deployment Log: {log_file.name}")
    print(f"{'='*60}")
    print(f"🔗 Repository: {data.get('repo_url', 'N/A')}")
    print(f"🖥️  Target:     {data.get('target', 'N/A')}")
    print(f"⏰ Started:    {data.get('start_time', 'N/A')}")
    print(f"⏱️  Ended:      {data.get('end_time', 'N/A')}")
    print(f"{status_emoji} Status:     {status}")
    print(f"📊 Steps:      {len(data.get('steps', []))}")
    print(f"{'='*60}\n")
    
    steps = data.get("steps", [])
    
    for step in steps:
        iteration = step.get("iteration", "?")
        action = step.get("action", "?")
        command = step.get("command", "")
        reasoning = step.get("reasoning", "")
        result = step.get("result", {})
        
        # 确定状态符号
        if action == "done":
            status_icon = "✅"
        elif action == "failed":
            status_icon = "❌"
        elif isinstance(result, dict) and result.get("success"):
            status_icon = "✓"
        elif isinstance(result, dict) and not result.get("success"):
            status_icon = "✗"
        else:
            status_icon = "•"
        
        print(f"[{iteration}] {status_icon} {action.upper()}")
        
        if reasoning:
            print(f"    💭 {reasoning}")
        
        if command:
            print(f"    $ {command}")
        
        if step.get("message"):
            print(f"    📝 {step.get('message')}")
        
        if not summary_only and isinstance(result, dict):
            exit_code = result.get("exit_code", "")
            stdout = result.get("stdout", "").strip()
            stderr = result.get("stderr", "").strip()
            
            if exit_code != "":
                print(f"    Exit: {exit_code}")
            
            if stdout:
                # 限制输出长度
                lines = stdout.split("\n")[:10]
                for line in lines:
                    print(f"    │ {line[:100]}")
                if len(stdout.split("\n")) > 10:
                    print(f"    │ ... ({len(stdout.split(chr(10)))} lines total)")
            
            if stderr and not result.get("success"):
                print(f"    ⚠️ stderr:")
                lines = stderr.split("\n")[:5]
                for line in lines:
                    print(f"    │ {line[:100]}")
        
        print()
    
    print(f"{'='*60}")
    print(f"📄 Full log: {log_file}")
    print(f"{'='*60}\n")


def dispatch_command(args: argparse.Namespace) -> int:
    context = _build_context(args)
    
    # 处理 logs 命令
    if args.command == "logs":
        return handle_logs_command(args)
    
    workflow = DeploymentWorkflow(
        config=context.config,
        workspace=context.workspace,
    )

    if args.command == "deploy":
        # 检查是否是本地部署模式
        if getattr(args, "local", False):
            # 本地部署模式
            from .workflow import LocalDeploymentRequest
            
            deploy_dir = args.deploy_dir  # 可以为 None，workflow 会使用默认值
            request = LocalDeploymentRequest(
                repo_url=args.repo,
                deploy_dir=deploy_dir,
            )
            workflow.run_local_deploy(request)
            return 0
        
        # SSH 远程部署模式
        deployment = context.config.deployment
        host = args.host or deployment.default_host
        port = args.port or deployment.default_port
        username = args.user or deployment.default_username
        auth_method = args.auth_method or deployment.default_auth_method
        password = args.password if args.password is not None else deployment.default_password
        key_path = args.key_path if args.key_path is not None else deployment.default_key_path
        missing = []
        if not host:
            missing.append("host")
        if not username:
            missing.append("user")
        if not auth_method:
            missing.append("auth-method")
        if auth_method == "password" and not password:
            missing.append("password")
        if auth_method == "key" and not key_path:
            missing.append("key-path")
        if missing:
            raise ValueError(
                "Missing SSH connection values: " + ", ".join(missing)
            )
        assert host is not None
        assert port is not None
        assert username is not None
        assert auth_method is not None
        request = DeploymentRequest(
            repo_url=args.repo,
            host=host,
            port=port,
            username=username,
            auth_method=auth_method,
            password=password,
            key_path=key_path,
        )
        workflow.run_deploy(request)
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


def run_cli(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch_command(args)
