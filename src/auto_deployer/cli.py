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
    
    # 部署目录（适用于本地和远程模式）
    deploy_parser.add_argument(
        "--deploy-dir", type=str, default=None,
        help="Target directory for deployment (default: ~/<repo_name>)"
    )
    
    # 本地部署模式
    deploy_parser.add_argument(
        "--local", "-L", action="store_true",
        help="Deploy locally on this machine (no SSH needed)"
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

    # memory 子命令 - 管理知识库
    memory_parser = subparsers.add_parser(
        "memory", help="Manage agent's experience memory"
    )
    memory_parser.add_argument(
        "--status", action="store_true",
        help="Show memory status and statistics"
    )
    memory_parser.add_argument(
        "--extract", action="store_true",
        help="Extract experiences from deployment logs"
    )
    memory_parser.add_argument(
        "--refine", action="store_true",
        help="Refine raw experiences using LLM"
    )
    memory_parser.add_argument(
        "--list", "-l", action="store_true", dest="list_experiences",
        help="List all stored experiences"
    )
    memory_parser.add_argument(
        "--show", type=int, metavar="N",
        help="Show detailed view of experience #N"
    )
    memory_parser.add_argument(
        "--export", choices=["json", "markdown", "md"],
        help="Export memories to human-readable file (json/markdown)"
    )
    memory_parser.add_argument(
        "--clear", action="store_true",
        help="Clear all stored experiences (with confirmation)"
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


def handle_memory_command(args: argparse.Namespace, context: CLIContext) -> int:
    """Handle the memory subcommand."""
    from .knowledge import ExperienceStore, ExperienceExtractor, ExperienceRefiner
    from .paths import get_memory_dir
    
    store = ExperienceStore()
    
    if args.status:
        # 显示状态
        try:
            stats = store.get_stats()
            print(f"\n{'='*50}")
            print("🧠 Agent Memory Status")
            print(f"{'='*50}")
            print(f"📁 Storage:         {stats['persist_dir']}")
            print(f"📥 Raw experiences: {stats['raw_count']}")
            print(f"   └ Unprocessed:   {stats['unprocessed_count']}")
            print(f"📊 Refined:         {stats['refined_count']}")
            print(f"   ├ Universal:     {stats['universal_count']}")
            print(f"   └ Proj-specific: {stats['project_specific_count']}")
            if stats['project_types']:
                print(f"\n📦 By Project Type:")
                for pt, count in stats['project_types'].items():
                    print(f"   • {pt}: {count}")
            print(f"{'='*50}\n")
        except ImportError as e:
            print(f"❌ Missing dependencies: {e}")
            print("   Install with: pip install chromadb sentence-transformers")
            return 1
        return 0
    
    if args.extract:
        # 从日志提取经验
        print("📤 Extracting experiences from deployment logs...")
        extractor = ExperienceExtractor()
        experiences = extractor.extract_from_all_logs()
        
        added = 0
        skipped = 0
        for exp in experiences:
            if store.raw_exists(exp.id):
                skipped += 1
            else:
                store.add_raw_experience(
                    id=exp.id,
                    content=exp.content,
                    metadata={
                        "project_type": exp.project_type or "unknown",
                        "framework": exp.framework or "",
                        "source_log": exp.source_log,
                        "timestamp": exp.timestamp,
                        "processed": "False",
                    }
                )
                added += 1
        
        store.persist()
        print(f"✅ Extracted: {added} new, {skipped} already exist")
        return 0
    
    if args.refine:
        # 使用 LLM 精炼经验
        unprocessed = store.get_unprocessed_raw_experiences()
        if not unprocessed:
            print("ℹ️  No unprocessed experiences to refine")
            return 0
        
        print(f"🔄 Refining {len(unprocessed)} experiences with LLM...")
        
        # 创建简单的 LLM 包装器
        class SimpleLLM:
            def __init__(self, config):
                import requests
                self.config = config
                self.session = requests.Session()
                self.endpoint = config.endpoint or (
                    f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent"
                )
                proxy = config.proxy
                if proxy:
                    self.session.proxies = {"http": proxy, "https": proxy}
            
            def generate(self, prompt: str) -> str:
                url = f"{self.endpoint}?key={self.config.api_key}"
                body = {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3},
                }
                resp = self.session.post(url, json=body, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                candidates = data.get("candidates") or []
                for c in candidates:
                    parts = c.get("content", {}).get("parts", [])
                    for p in parts:
                        if p.get("text"):
                            return p["text"]
                return ""
        
        llm = SimpleLLM(context.config.llm)
        refiner = ExperienceRefiner(llm)
        
        refined_count = 0
        for exp in unprocessed:
            print(f"  Processing: {exp['id'][:12]}...", end=" ")
            refined = refiner.refine(exp)
            if refined:
                if not store.refined_exists(refined["id"]):
                    store.add_refined_experience(
                        id=refined["id"],
                        content=refined["content"],
                        metadata=refined["metadata"]
                    )
                store.mark_raw_as_processed(exp["id"])
                scope = refined["metadata"].get("scope", "unknown")
                print(f"✓ [{scope}]")
                refined_count += 1
            else:
                print("✗ failed")
        
        store.persist()
        print(f"\n✅ Refined {refined_count}/{len(unprocessed)} experiences")
        return 0
    
    if args.list_experiences:
        # 列出所有经验
        refined = store.get_all_refined_experiences()
        if not refined:
            print("ℹ️  No refined experiences stored")
            return 0
        
        print(f"\n{'='*70}")
        print(f"🧠 Stored Experiences ({len(refined)} total)")
        print(f"{'='*70}\n")
        
        for i, exp in enumerate(refined, 1):
            meta = exp.get("metadata", {})
            scope = meta.get("scope", "unknown")
            scope_icon = "🌍" if scope == "universal" else "📦"
            problem = meta.get("problem_summary", "?")
            solution = meta.get("solution_summary", "?")
            project_type = meta.get("project_type", "")
            framework = meta.get("framework", "")
            
            print(f"{i:2}. {scope_icon} [{scope.upper()}] {problem}")
            print(f"    💡 Solution: {solution}")
            if project_type or framework:
                tags = [t for t in [project_type, framework] if t]
                print(f"    🏷️  Tags: {', '.join(tags)}")
            print()
        
        print(f"{'='*70}")
        print(f"💡 Use `auto-deployer memory --show N` to view details of experience #N")
        print(f"💡 Use `auto-deployer memory --export markdown` to export all memories")
        print(f"{'='*70}\n")
        
        return 0
    
    if args.show:
        # 显示单个经验的详细信息
        refined = store.get_all_refined_experiences()
        idx = args.show - 1
        
        if idx < 0 or idx >= len(refined):
            print(f"❌ Experience #{args.show} not found. Valid range: 1-{len(refined)}")
            return 1
        
        exp = refined[idx]
        meta = exp.get("metadata", {})
        
        print(f"\n{'='*70}")
        print(f"🧠 Experience #{args.show} - Detailed View")
        print(f"{'='*70}\n")
        
        print(f"📋 ID:           {exp.get('id', 'N/A')}")
        print(f"🏷️  Scope:        {meta.get('scope', 'N/A')}")
        print(f"📦 Project Type: {meta.get('project_type', 'N/A')}")
        print(f"🔧 Framework:    {meta.get('framework', 'N/A')}")
        print(f"📅 Source Log:   {meta.get('source_log', 'N/A')}")
        
        print(f"\n{'─'*70}")
        print("❌ PROBLEM:")
        print(f"{'─'*70}")
        print(f"   {meta.get('problem_summary', 'N/A')}")
        
        print(f"\n{'─'*70}")
        print("✅ SOLUTION:")
        print(f"{'─'*70}")
        print(f"   {meta.get('solution_summary', 'N/A')}")
        
        print(f"\n{'─'*70}")
        print("📝 FULL EXPERIENCE:")
        print(f"{'─'*70}")
        content = exp.get('content', '')
        # 格式化显示
        for line in content.split('\n'):
            print(f"   {line}")
        
        print(f"\n{'='*70}\n")
        return 0
    
    if args.export:
        # 导出记忆到可读文件
        refined = store.get_all_refined_experiences()
        raw = store.get_all_raw_experiences()
        
        if not refined and not raw:
            print("ℹ️  No experiences to export")
            return 0
        
        memory_dir = get_memory_dir()
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if args.export == "json":
            # 导出为 JSON
            export_file = memory_dir / f"memories_{timestamp}.json"
            export_data = {
                "export_time": datetime.now().isoformat(),
                "statistics": {
                    "raw_count": len(raw),
                    "refined_count": len(refined),
                },
                "refined_experiences": [
                    {
                        "id": exp.get("id"),
                        "problem": exp.get("metadata", {}).get("problem_summary"),
                        "solution": exp.get("metadata", {}).get("solution_summary"),
                        "scope": exp.get("metadata", {}).get("scope"),
                        "project_type": exp.get("metadata", {}).get("project_type"),
                        "framework": exp.get("metadata", {}).get("framework"),
                        "content": exp.get("content"),
                    }
                    for exp in refined
                ],
                "raw_experiences": [
                    {
                        "id": exp.get("id"),
                        "content": exp.get("content"),
                        "metadata": exp.get("metadata"),
                    }
                    for exp in raw
                ]
            }
            
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            print(f"✅ Exported {len(refined)} refined + {len(raw)} raw experiences to:")
            print(f"   📄 {export_file}")
            
        else:  # markdown or md
            # 导出为 Markdown
            export_file = memory_dir / f"memories_{timestamp}.md"
            
            lines = [
                "# 🧠 Auto-Deployer Memory Export",
                f"",
                f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"**精炼经验数**: {len(refined)}",
                f"**原始经验数**: {len(raw)}",
                "",
                "---",
                "",
                "## 📚 精炼经验库",
                "",
            ]
            
            # 按类型分组
            universal = [e for e in refined if e.get("metadata", {}).get("scope") == "universal"]
            project_specific = [e for e in refined if e.get("metadata", {}).get("scope") == "project_specific"]
            
            if universal:
                lines.append("### 🌍 通用经验")
                lines.append("")
                for i, exp in enumerate(universal, 1):
                    meta = exp.get("metadata", {})
                    lines.append(f"#### {i}. {meta.get('problem_summary', 'Unknown Problem')}")
                    lines.append("")
                    lines.append(f"- **问题**: {meta.get('problem_summary', 'N/A')}")
                    lines.append(f"- **解决方案**: {meta.get('solution_summary', 'N/A')}")
                    lines.append(f"- **项目类型**: {meta.get('project_type', 'N/A')}")
                    if meta.get('framework'):
                        lines.append(f"- **框架**: {meta.get('framework')}")
                    lines.append("")
                    lines.append("<details>")
                    lines.append("<summary>📝 详细内容</summary>")
                    lines.append("")
                    lines.append("```")
                    lines.append(exp.get("content", ""))
                    lines.append("```")
                    lines.append("</details>")
                    lines.append("")
            
            if project_specific:
                lines.append("### 📦 项目特定经验")
                lines.append("")
                for i, exp in enumerate(project_specific, 1):
                    meta = exp.get("metadata", {})
                    lines.append(f"#### {i}. {meta.get('problem_summary', 'Unknown Problem')}")
                    lines.append("")
                    lines.append(f"- **问题**: {meta.get('problem_summary', 'N/A')}")
                    lines.append(f"- **解决方案**: {meta.get('solution_summary', 'N/A')}")
                    lines.append(f"- **项目类型**: {meta.get('project_type', 'N/A')}")
                    if meta.get('framework'):
                        lines.append(f"- **框架**: {meta.get('framework')}")
                    lines.append("")
                    lines.append("<details>")
                    lines.append("<summary>📝 详细内容</summary>")
                    lines.append("")
                    lines.append("```")
                    lines.append(exp.get("content", ""))
                    lines.append("```")
                    lines.append("</details>")
                    lines.append("")
            
            lines.append("---")
            lines.append("")
            lines.append("*此文件由 Auto-Deployer 自动生成*")
            
            with open(export_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            
            print(f"✅ Exported {len(refined)} experiences to Markdown:")
            print(f"   📄 {export_file}")
        
        return 0
    
    if args.clear:
        # 清除所有经验
        confirm = input("⚠️  Clear all stored experiences? (type 'yes' to confirm): ")
        if confirm.lower() == "yes":
            import shutil
            shutil.rmtree(store.persist_dir, ignore_errors=True)
            print("✅ Memory cleared")
        else:
            print("❌ Cancelled")
        return 0
    
    # 默认显示状态
    return handle_memory_command(
        argparse.Namespace(
            status=True, extract=False, refine=False,
            list_experiences=False, show=None, export=None, clear=False
        ),
        context
    )


def dispatch_command(args: argparse.Namespace) -> int:
    context = _build_context(args)
    
    # 处理 logs 命令
    if args.command == "logs":
        return handle_logs_command(args)
    
    # 处理 memory 命令
    if args.command == "memory":
        return handle_memory_command(args, context)
    
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
            deploy_dir=args.deploy_dir,  # 可以为 None，会使用仓库名
        )
        workflow.run_deploy(request)
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


def run_cli(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return dispatch_command(args)
