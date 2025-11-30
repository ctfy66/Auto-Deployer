"""Repository analyzer implementation."""

from __future__ import annotations

from typing import List

from .insights import RepositoryInsights
from ..workspace import WorkspaceContext


class RepositoryAnalyzer:
    """Performs lightweight heuristics on the prepared workspace."""

    TARGET_FILES = {
        "package.json": "node",
        "requirements.txt": "python",
        "pyproject.toml": "python",
        "Pipfile": "python",
        "Dockerfile": "docker",
        "docker-compose.yml": "docker-compose",
    }

    # 常见的入口文件和部署脚本
    ENTRY_POINT_FILES = [
        "app.py", "main.py", "server.py", "run.py", "wsgi.py",
        "index.js", "server.js", "app.js", "main.js",
        "deploy.sh", "start.sh", "run.sh", "setup.sh",
        "Makefile", "Procfile",
    ]

    def analyze(self, context: WorkspaceContext) -> RepositoryInsights:
        repo_dir = context.source_dir
        detected = {name: (repo_dir / name).is_file() for name in self.TARGET_FILES}
        languages = self._detect_languages(detected)
        hints = self._build_hints(detected)
        
        # 检测入口文件
        entry_points = self._detect_entry_points(repo_dir)
        
        # 获取仓库的文件列表（只列出根目录的重要文件）
        file_list = self._list_repo_files(repo_dir)
        
        return RepositoryInsights(
            source_dir=repo_dir,
            languages=languages,
            deployment_hints=hints,
            detected_files=detected,
            entry_points=entry_points,
            file_list=file_list,
        )

    def _detect_languages(self, detected: dict[str, bool]) -> List[str]:
        langs = set()
        for filename, language in self.TARGET_FILES.items():
            if detected.get(filename):
                if language in {"docker", "docker-compose"}:
                    continue
                langs.add(language)
        return sorted(langs)

    def _build_hints(self, detected: dict[str, bool]) -> List[str]:
        hints: List[str] = []
        if detected.get("Dockerfile"):
            hints.append("dockerfile-present")
        if detected.get("docker-compose.yml"):
            hints.append("docker-compose-present")
        if detected.get("package.json"):
            hints.append("node-npm")
        if detected.get("requirements.txt"):
            hints.append("python-pip")
        if detected.get("pyproject.toml"):
            hints.append("python-pyproject")
        if detected.get("Pipfile"):
            hints.append("python-pipenv")
        return hints

    def _detect_entry_points(self, repo_dir) -> List[str]:
        """检测可能的入口文件和部署脚本。"""
        found = []
        for filename in self.ENTRY_POINT_FILES:
            if (repo_dir / filename).is_file():
                found.append(filename)
        return found

    def _list_repo_files(self, repo_dir) -> List[str]:
        """列出仓库根目录的文件（排除隐藏文件和目录）。"""
        files = []
        try:
            for item in repo_dir.iterdir():
                if item.name.startswith('.'):
                    continue
                if item.is_file():
                    files.append(item.name)
        except Exception:
            pass
        return sorted(files)
