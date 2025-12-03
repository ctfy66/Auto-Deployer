"""Unified path constants for Auto-Deployer.

All data is stored under .auto-deployer directory:
- .auto-deployer/workspace/   # Local repo clones for analysis
- .auto-deployer/knowledge/   # ChromaDB vector store
- .auto-deployer/memory/      # Human-readable memory exports
"""

from pathlib import Path

# 基础目录（在当前工作目录下）
BASE_DIR = Path(".auto-deployer")

# 各子目录
WORKSPACE_DIR = BASE_DIR / "workspace"    # 本地仓库克隆
KNOWLEDGE_DIR = BASE_DIR / "knowledge"    # ChromaDB 向量存储
MEMORY_DIR = BASE_DIR / "memory"          # 可读记忆导出
LOGS_DIR = Path("agent_logs")             # Agent 日志（保持向后兼容）


def ensure_dirs() -> None:
    """确保所有必要目录存在."""
    BASE_DIR.mkdir(exist_ok=True)
    WORKSPACE_DIR.mkdir(exist_ok=True)
    # knowledge 和 memory 目录按需创建


def get_workspace_dir() -> Path:
    """获取 workspace 目录路径."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    return WORKSPACE_DIR


def get_knowledge_dir() -> Path:
    """获取 knowledge 目录路径."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    return KNOWLEDGE_DIR


def get_memory_dir() -> Path:
    """获取 memory 目录路径（人类可读导出）."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    return MEMORY_DIR
