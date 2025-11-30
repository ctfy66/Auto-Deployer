"""Command-line interface for Auto-Deployer."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Optional

from .config import AppConfig, load_config
from .workflow import DeploymentRequest, DeploymentWorkflow


@dataclass
class CLIContext:
    """Context captured from CLI arguments."""

    config: AppConfig
    workspace: str
    max_retries: Optional[int]


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
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Override retry count for this run.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    deploy_parser = subparsers.add_parser(
        "deploy", help="Trigger a deployment for a GitHub repository"
    )
    deploy_parser.add_argument("--repo", required=True, help="Git repository URL")
    deploy_parser.add_argument("--host", help="Target server host")
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

    return parser


def _build_context(args: argparse.Namespace) -> CLIContext:
    config = load_config(args.config)
    workspace = args.workspace or config.deployment.workspace_root
    return CLIContext(
        config=config,
        workspace=workspace,
        max_retries=args.max_retries,
    )


def dispatch_command(args: argparse.Namespace) -> int:
    context = _build_context(args)
    workflow = DeploymentWorkflow(
        config=context.config,
        workspace=context.workspace,
        max_retries=context.max_retries,
    )

    if args.command == "deploy":
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
