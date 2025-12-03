"""Data models for experience storage."""

from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class ResolutionStep:
    """A single step in a resolution chain."""
    
    index: int
    command: str
    success: bool
    stdout: str
    stderr: str
    reasoning: str
    is_diagnostic: bool  # ls, cat, echo 等诊断命令


@dataclass
class ResolutionChain:
    """A complete chain from error to resolution."""
    
    id: str
    start_index: int
    end_index: int
    steps: List[ResolutionStep]
    
    # 初始错误信息
    initial_command: str
    initial_error: str
    
    # 最终解决方案
    resolution_command: str
    resolution_reasoning: str
    
    # 上下文
    project_type: str
    framework: Optional[str]
    source_log: str
    timestamp: str
    
    def get_full_content(self) -> str:
        """生成完整的经验内容，用于向量化存储"""
        lines = []
        lines.append(f"## Problem: {self.initial_command[:100]}")
        lines.append(f"Error: {self.initial_error[:200]}")
        lines.append("")
        lines.append("### Resolution Process:")
        
        for step in self.steps:
            status = "✅" if step.success else "❌"
            cmd_preview = step.command[:80] + "..." if len(step.command) > 80 else step.command
            if step.is_diagnostic:
                lines.append(f"  {status} [DIAG] {cmd_preview}")
            else:
                lines.append(f"  {status} {cmd_preview}")
            if step.reasoning:
                lines.append(f"      Reason: {step.reasoning[:100]}")
        
        lines.append("")
        lines.append(f"### Solution: {self.resolution_command}")
        lines.append(f"Why: {self.resolution_reasoning}")
        
        return "\n".join(lines)


@dataclass
class RawExperience:
    """Raw experience extracted from logs, before LLM refinement."""
    
    id: str
    chain: ResolutionChain
    content: str  # 用于向量检索的内容
    
    # 元数据
    project_type: str
    framework: Optional[str]
    source_log: str
    timestamp: str
    processed: bool = False  # 是否已被 LLM 处理


@dataclass
class RefinedExperience:
    """Refined experience after LLM analysis."""
    
    id: str
    scope: str  # "universal" | "project_specific"
    
    # 结构化内容
    title: str
    problem: str
    solution: str
    explanation: str  # 原理解释
    tags: List[str] = field(default_factory=list)
    
    # 分类信息
    project_type: Optional[str] = None  # 仅 project_specific 时有值
    framework: Optional[str] = None
    
    # 来源
    source_raw_id: str = ""
    source_log: str = ""
    
    def get_content_for_prompt(self) -> str:
        """生成用于注入 prompt 的内容"""
        lines = [f"### {self.title}"]
        lines.append(f"**Problem**: {self.problem}")
        lines.append(f"**Solution**: {self.solution}")
        if self.explanation:
            lines.append(f"**Why**: {self.explanation}")
        return "\n".join(lines)
    
    def get_content_for_embedding(self) -> str:
        """生成用于向量化的内容"""
        parts = [
            self.title,
            self.problem,
            self.solution,
            self.explanation,
            " ".join(self.tags)
        ]
        return " ".join(parts)
