"""Workspace management for local repository analysis."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
import shutil


@dataclass
class WorkspaceContext:
    """Represents a prepared workspace for a single deployment request."""

    repo_url: str
    root: Path
    run_dir: Path
    source_dir: Path
    metadata_file: Path
    run_id: str


class WorkspaceManager:
    """Handles creation of per-request analysis directories."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def prepare(self, repo_url: str) -> WorkspaceContext:
        repo_slug = self._slugify_repo(repo_url)
        run_id = self._generate_run_id(repo_url)
        run_dir = self.root / f"{repo_slug}-{run_id}"
        source_dir = run_dir / "source"
        run_dir.mkdir(parents=True, exist_ok=True)
        source_dir.mkdir(parents=True, exist_ok=True)

        metadata_file = run_dir / "metadata.json"
        metadata = {
            "repo_url": repo_url,
            "created_at": int(time.time()),
            "run_id": run_id,
            "source_dir": str(source_dir),
        }
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return WorkspaceContext(
            repo_url=repo_url,
            root=self.root,
            run_dir=run_dir,
            source_dir=source_dir,
            metadata_file=metadata_file,
            run_id=run_id,
        )

    def cleanup(self, context: WorkspaceContext, *, delete_repo: bool = False) -> None:
        if delete_repo and context.run_dir.exists():
            shutil.rmtree(context.run_dir, ignore_errors=True)

    def update_metadata(self, context: WorkspaceContext, **fields: object) -> None:
        payload = {}
        if context.metadata_file.exists():
            payload = json.loads(context.metadata_file.read_text(encoding="utf-8"))
        payload.update(fields)
        context.metadata_file.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def read_metadata(self, context: WorkspaceContext) -> dict:
        if context.metadata_file.exists():
            return json.loads(context.metadata_file.read_text(encoding="utf-8"))
        return {}

    def _slugify_repo(self, repo_url: str) -> str:
        slug = repo_url.rstrip("/").split("/")[-1]
        if slug.endswith(".git"):
            slug = slug[:-4]
        return slug or "repository"

    def _generate_run_id(self, repo_url: str) -> str:
        token = f"{repo_url}-{time.time_ns()}".encode("utf-8")
        digest = hashlib.sha1(token).hexdigest()
        return digest[:8]
