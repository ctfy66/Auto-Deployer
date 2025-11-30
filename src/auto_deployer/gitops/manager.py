"""Git-based repository management."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class GitCommandError(RuntimeError):
    """Raised when a git command fails."""

    def __init__(self, command: list[str], exit_code: int, stderr: str) -> None:
        self.command = command
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(f"Git command {' '.join(command)} failed with code {exit_code}: {stderr}")


@dataclass
class GitCloneResult:
    """Details about a completed clone/update."""

    commit_sha: str


class GitRepositoryManager:
    """Wraps `git` CLI commands for cloning and updating repositories."""

    def __init__(self, git_binary: str = "git") -> None:
        self.git_binary = git_binary

    def clone_or_update(self, repo_url: str, target_dir: Path) -> GitCloneResult:
        target_dir = target_dir.resolve()
        if (target_dir / ".git").exists():
            self._run(["pull", "--ff-only"], cwd=target_dir)
        else:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            self._run(["clone", "--depth=1", repo_url, str(target_dir)])

        commit_sha = self._run(["rev-parse", "HEAD"], cwd=target_dir).strip()
        return GitCloneResult(commit_sha=commit_sha)

    def _run(self, args: list[str], cwd: Optional[Path] = None) -> str:
        command = [self.git_binary] + args
        process = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            raise GitCommandError(command, process.returncode, process.stderr.strip())
        return process.stdout
