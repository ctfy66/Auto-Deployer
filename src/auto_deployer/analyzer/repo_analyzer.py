"""Repository analyzer for extracting deployment-relevant context.

This module clones a repository locally and extracts key files that help
the LLM agent understand how to deploy the project.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# 关键文件列表（按重要性排序）
KEY_FILES = [
    # 部署说明
    "README.md",
    "README.rst",
    "DEPLOY.md",
    "DEPLOYMENT.md",
    
    # 包管理/依赖
    "package.json",
    "requirements.txt",
    "Pipfile",
    "pyproject.toml",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "composer.json",
    
    # 容器/部署
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
    
    # 环境配置
    ".env.example",
    ".env.sample",
    ".env.template",
    "env.example",
    
    # 构建配置
    "Makefile",
    "justfile",
    "Taskfile.yml",
    
    # 框架特定
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
    "nuxt.config.js",
    "nuxt.config.ts",
    "vue.config.js",
    "angular.json",
    "webpack.config.js",
    
    # 进程管理
    "Procfile",
    "ecosystem.config.js",
    "pm2.config.js",
    
    # CI/CD (可能有部署脚本参考)
    ".github/workflows/deploy.yml",
    ".github/workflows/ci.yml",
    ".gitlab-ci.yml",
]

# 文件大小限制（防止读取超大文件）
MAX_FILE_SIZE = 50 * 1024  # 50KB


@dataclass
class RepoContext:
    """Extracted context from a repository for deployment."""
    
    repo_url: str
    project_name: str
    
    # 检测到的项目类型
    project_type: Optional[str] = None  # nodejs, python, static, unknown
    
    # 关键文件内容
    files: Dict[str, str] = field(default_factory=dict)
    
    # 目录结构
    directory_tree: str = ""
    
    # 从 package.json/requirements.txt 提取的信息
    detected_framework: Optional[str] = None
    detected_scripts: Dict[str, str] = field(default_factory=dict)
    detected_dependencies: List[str] = field(default_factory=list)
    
    # 分析摘要
    summary: str = ""
    
    def to_prompt_context(self) -> str:
        """Convert to a string suitable for LLM prompt."""
        sections = []
        
        # 项目概述
        sections.append(f"# Repository Analysis: {self.project_name}")
        sections.append(f"- URL: {self.repo_url}")
        sections.append(f"- Detected Type: {self.project_type or 'unknown'}")
        if self.detected_framework:
            sections.append(f"- Framework: {self.detected_framework}")
        sections.append("")
        
        # 目录结构
        if self.directory_tree:
            sections.append("## Directory Structure")
            sections.append("```")
            sections.append(self.directory_tree)
            sections.append("```")
            sections.append("")
        
        # 脚本（如果是 Node.js 项目）
        if self.detected_scripts:
            sections.append("## Available Scripts (from package.json)")
            for name, cmd in self.detected_scripts.items():
                sections.append(f"- `npm run {name}`: {cmd}")
            sections.append("")
        
        # 关键文件内容
        if self.files:
            sections.append("## Key Files")
            for filename, content in self.files.items():
                sections.append(f"### {filename}")
                sections.append("```")
                # 截断超长内容
                if len(content) > 3000:
                    sections.append(content[:3000])
                    sections.append(f"... (truncated, {len(content)} chars total)")
                else:
                    sections.append(content)
                sections.append("```")
                sections.append("")
        
        return "\n".join(sections)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class RepoAnalyzer:
    """Analyzes a git repository to extract deployment context."""
    
    def __init__(self, workspace_dir: Optional[str] = None):
        """Initialize analyzer with optional workspace directory."""
        self.workspace_dir = Path(workspace_dir) if workspace_dir else None
    
    def analyze(self, repo_url: str) -> RepoContext:
        """
        Clone and analyze a repository.
        
        Args:
            repo_url: Git repository URL
            
        Returns:
            RepoContext with extracted information
        """
        # 提取项目名
        project_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
        
        # 创建临时目录或使用配置的工作目录
        if self.workspace_dir:
            clone_dir = self.workspace_dir / project_name
            clone_dir.parent.mkdir(parents=True, exist_ok=True)
            if clone_dir.exists():
                self._safe_rmtree(clone_dir)
            cleanup = False
        else:
            temp_dir = tempfile.mkdtemp(prefix="auto-deployer-")
            clone_dir = Path(temp_dir) / project_name
            cleanup = True
        
        try:
            # 克隆仓库
            logger.info(f"Cloning {repo_url} to {clone_dir}...")
            self._clone_repo(repo_url, clone_dir)
            
            # 创建上下文对象
            context = RepoContext(
                repo_url=repo_url,
                project_name=project_name,
            )
            
            # 读取关键文件
            self._read_key_files(clone_dir, context)
            
            # 生成目录树
            context.directory_tree = self._generate_tree(clone_dir)
            
            # 检测项目类型
            self._detect_project_type(context)
            
            # 提取额外信息
            self._extract_metadata(context)
            
            # 生成摘要
            context.summary = self._generate_summary(context)
            
            logger.info(f"Analysis complete: {context.project_type} project")
            return context
            
        finally:
            # 清理临时目录
            if cleanup and clone_dir.parent.exists():
                self._safe_rmtree(clone_dir.parent)
    
    def _safe_rmtree(self, path: Path) -> None:
        """Safely remove a directory tree, handling Windows permission errors."""
        import stat
        import time
        
        def on_rm_error(func, path, exc_info):
            """Error handler for shutil.rmtree on Windows."""
            # 尝试修改权限后重试
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception:
                pass  # 忽略无法删除的文件
        
        # 尝试多次删除（处理文件被短暂锁定的情况）
        for attempt in range(3):
            try:
                shutil.rmtree(path, onerror=on_rm_error)
                return
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.5)  # 等待文件锁释放
                else:
                    logger.warning(f"Could not fully clean up {path}: {e}")
    
    def _clone_repo(self, repo_url: str, target_dir: Path) -> None:
        """Clone a git repository."""
        cmd = ["git", "clone", "--depth", "1", repo_url, str(target_dir)]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr}")
    
    def _read_key_files(self, repo_dir: Path, context: RepoContext) -> None:
        """Read key files from the repository."""
        for filename in KEY_FILES:
            file_path = repo_dir / filename
            if file_path.exists() and file_path.is_file():
                # 检查文件大小
                if file_path.stat().st_size > MAX_FILE_SIZE:
                    logger.warning(f"Skipping {filename}: too large")
                    continue
                
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    context.files[filename] = content
                    logger.debug(f"Read {filename} ({len(content)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to read {filename}: {e}")
    
    def _generate_tree(self, repo_dir: Path, max_depth: int = 3) -> str:
        """Generate a directory tree string."""
        lines = []
        
        def walk(path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return
            
            # 忽略的目录
            ignore = {".git", "node_modules", "__pycache__", ".venv", "venv", 
                     "dist", "build", ".next", ".nuxt", "target", "vendor"}
            
            try:
                entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return
            
            # 过滤
            entries = [e for e in entries if e.name not in ignore]
            
            for i, entry in enumerate(entries[:20]):  # 限制每层最多20项
                is_last = i == len(entries[:20]) - 1
                connector = "└── " if is_last else "├── "
                
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}/")
                    extension = "    " if is_last else "│   "
                    walk(entry, prefix + extension, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")
            
            if len(entries) > 20:
                lines.append(f"{prefix}... and {len(entries) - 20} more")
        
        lines.append(f"{repo_dir.name}/")
        walk(repo_dir)
        return "\n".join(lines)
    
    def _detect_project_type(self, context: RepoContext) -> None:
        """Detect the project type based on files."""
        files = set(context.files.keys())
        
        if "package.json" in files:
            context.project_type = "nodejs"
            # 进一步检测框架
            pkg = context.files.get("package.json", "")
            if "next" in pkg.lower():
                context.detected_framework = "Next.js"
            elif "nuxt" in pkg.lower():
                context.detected_framework = "Nuxt"
            elif "vite" in pkg.lower() or "vite.config" in str(files):
                context.detected_framework = "Vite"
            elif "vue" in pkg.lower():
                context.detected_framework = "Vue"
            elif "react" in pkg.lower():
                context.detected_framework = "React"
            elif "express" in pkg.lower():
                context.detected_framework = "Express"
                
        elif "requirements.txt" in files or "pyproject.toml" in files or "Pipfile" in files:
            context.project_type = "python"
            # 检测框架
            reqs = context.files.get("requirements.txt", "") + context.files.get("pyproject.toml", "")
            if "flask" in reqs.lower():
                context.detected_framework = "Flask"
            elif "django" in reqs.lower():
                context.detected_framework = "Django"
            elif "fastapi" in reqs.lower():
                context.detected_framework = "FastAPI"
                
        elif "go.mod" in files:
            context.project_type = "go"
        elif "Cargo.toml" in files:
            context.project_type = "rust"
        elif "pom.xml" in files or "build.gradle" in files:
            context.project_type = "java"
        elif "Gemfile" in files:
            context.project_type = "ruby"
        elif "composer.json" in files:
            context.project_type = "php"
        else:
            # 检查是否是静态站点
            if any(f.endswith((".html", ".htm")) for f in files):
                context.project_type = "static"
            else:
                context.project_type = "unknown"
    
    def _extract_metadata(self, context: RepoContext) -> None:
        """Extract metadata from configuration files."""
        # 从 package.json 提取脚本
        if "package.json" in context.files:
            try:
                pkg = json.loads(context.files["package.json"])
                scripts = pkg.get("scripts", {})
                context.detected_scripts = scripts
                
                # 提取主要依赖
                deps = list(pkg.get("dependencies", {}).keys())
                dev_deps = list(pkg.get("devDependencies", {}).keys())
                context.detected_dependencies = deps[:10] + dev_deps[:5]  # 限制数量
            except json.JSONDecodeError:
                pass
        
        # 从 requirements.txt 提取依赖
        elif "requirements.txt" in context.files:
            lines = context.files["requirements.txt"].strip().split("\n")
            deps = [l.split("==")[0].split(">=")[0].strip() for l in lines if l.strip() and not l.startswith("#")]
            context.detected_dependencies = deps[:15]
    
    def _generate_summary(self, context: RepoContext) -> str:
        """Generate a brief summary of the analysis."""
        parts = [f"{context.project_type or 'Unknown'} project"]
        
        if context.detected_framework:
            parts.append(f"using {context.detected_framework}")
        
        if context.detected_dependencies:
            parts.append(f"with {len(context.detected_dependencies)} dependencies")
        
        key_files = list(context.files.keys())
        if key_files:
            parts.append(f"({len(key_files)} key files found)")
        
        return " ".join(parts)
