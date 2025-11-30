"""Data structures describing repository insights."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class RepositoryInsights:
    """Lightweight signals derived from local repository inspection."""

    source_dir: Path
    languages: List[str] = field(default_factory=list)
    deployment_hints: List[str] = field(default_factory=list)
    detected_files: Dict[str, bool] = field(default_factory=dict)
    entry_points: List[str] = field(default_factory=list)
    file_list: List[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "source_dir": str(self.source_dir),
            "languages": self.languages,
            "deployment_hints": self.deployment_hints,
            "detected_files": self.detected_files,
            "entry_points": self.entry_points,
            "file_list": self.file_list,
        }
