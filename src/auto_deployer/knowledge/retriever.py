"""Retrieve relevant experiences for prompt injection."""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

from .store import ExperienceStore

logger = logging.getLogger(__name__)


class ExperienceRetriever:
    """检索相关经验用于 prompt 注入"""
    
    def __init__(self, store: ExperienceStore):
        self.store = store
    
    def get_relevant_experiences(
        self,
        project_type: Optional[str] = None,
        framework: Optional[str] = None,
        query: Optional[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取相关经验
        
        策略:
        1. 所有 universal 经验
        2. 匹配 project_type 或 framework 的 project_specific 经验
        3. 如果提供了 query，用语义搜索补充
        
        Args:
            project_type: 项目类型 (如 "nodejs", "python")
            framework: 框架 (如 "vitepress", "flask")
            query: 可选的搜索查询
            max_results: 最大返回数量
        
        Returns:
            相关经验列表
        """
        experiences = []
        seen_ids = set()
        
        # 1. 获取所有 universal 经验
        universal = self._get_universal_experiences()
        for exp in universal:
            if exp["id"] not in seen_ids:
                experiences.append(exp)
                seen_ids.add(exp["id"])
        
        # 2. 获取匹配的 project_specific 经验
        if project_type or framework:
            specific = self._get_project_specific_experiences(project_type, framework)
            for exp in specific:
                if exp["id"] not in seen_ids:
                    experiences.append(exp)
                    seen_ids.add(exp["id"])
        
        # 3. 如果提供了 query，用语义搜索补充
        if query and len(experiences) < max_results:
            remaining = max_results - len(experiences)
            search_results = self.store.search_refined(query, n_results=remaining)
            for exp in search_results:
                if exp["id"] not in seen_ids:
                    experiences.append(exp)
                    seen_ids.add(exp["id"])
        
        # 按 confidence 排序
        experiences.sort(
            key=lambda x: float(x.get("metadata", {}).get("confidence", 0)),
            reverse=True
        )
        
        return experiences[:max_results]
    
    def _get_universal_experiences(self) -> List[Dict[str, Any]]:
        """获取所有 universal 经验"""
        all_refined = self.store.get_all_refined_experiences()
        return [
            exp for exp in all_refined
            if exp.get("metadata", {}).get("scope") == "universal"
        ]
    
    def _get_project_specific_experiences(
        self,
        project_type: Optional[str],
        framework: Optional[str]
    ) -> List[Dict[str, Any]]:
        """获取匹配的 project_specific 经验"""
        all_refined = self.store.get_all_refined_experiences()
        
        matching = []
        for exp in all_refined:
            meta = exp.get("metadata", {})
            
            if meta.get("scope") != "project_specific":
                continue
            
            # 检查项目类型匹配
            exp_project_type = meta.get("project_type", "").lower()
            exp_framework = meta.get("framework", "").lower()
            
            if project_type and project_type.lower() in exp_project_type:
                matching.append(exp)
            elif framework and framework.lower() in exp_framework:
                matching.append(exp)
            elif framework and framework.lower() in meta.get("keywords", "").lower():
                matching.append(exp)
        
        return matching
    
    def format_for_prompt(
        self,
        experiences: List[Dict[str, Any]],
        max_length: int = 3000
    ) -> str:
        """
        将经验格式化为可注入 prompt 的文本
        
        Args:
            experiences: 经验列表
            max_length: 最大字符数
        
        Returns:
            格式化的文本
        """
        if not experiences:
            return ""
        
        lines = ["## Past Deployment Experiences", ""]
        lines.append("The following are lessons learned from previous deployments:")
        lines.append("")
        
        current_length = sum(len(line) for line in lines)
        
        for i, exp in enumerate(experiences, 1):
            meta = exp.get("metadata", {})
            
            scope = meta.get("scope", "unknown").upper()
            problem = meta.get("problem_summary", "Unknown problem")
            solution = meta.get("solution_summary", "Unknown solution")
            lesson = meta.get("lesson", "")
            framework = meta.get("framework", "")
            
            entry_lines = [
                f"### Experience {i} [{scope}]",
                f"**Problem**: {problem}",
                f"**Solution**: {solution}",
            ]
            
            if lesson:
                entry_lines.append(f"**Lesson**: {lesson}")
            
            if framework:
                entry_lines.append(f"**Framework**: {framework}")
            
            entry_lines.append("")
            
            entry_text = "\n".join(entry_lines)
            
            if current_length + len(entry_text) > max_length:
                lines.append("... (more experiences omitted due to length)")
                break
            
            lines.extend(entry_lines)
            current_length += len(entry_text)
        
        return "\n".join(lines)
    
    def get_formatted_experiences(
        self,
        project_type: Optional[str] = None,
        framework: Optional[str] = None,
        query: Optional[str] = None,
        max_results: int = 10,
        max_length: int = 3000
    ) -> str:
        """
        便捷方法：获取并格式化经验
        
        Returns:
            格式化的经验文本，可直接注入 prompt
        """
        experiences = self.get_relevant_experiences(
            project_type=project_type,
            framework=framework,
            query=query,
            max_results=max_results
        )
        
        return self.format_for_prompt(experiences, max_length=max_length)
