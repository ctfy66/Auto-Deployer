"""Use LLM to refine raw experiences."""

from __future__ import annotations

import logging
import json
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# 用于分析和分类经验的 Prompt
REFINE_PROMPT = """你是一个部署经验分析专家。请分析以下从部署日志中提取的问题修复记录。

## 原始记录

{raw_content}

## 任务

1. **问题分析**: 总结出现的核心问题是什么
2. **解决方案**: 总结最终的解决方法
3. **关键教训**: 提炼出可复用的经验教训
4. **分类**: 判断这个经验的适用范围
   - `universal`: 通用经验，适用于所有项目（如 Linux 命令、Nginx 配置、SSH 权限等）
   - `project_specific`: 项目特定经验，只适用于特定框架或技术栈（如 VitePress、Flask 特有问题）
5. **关键词**: 提取与此问题相关的关键词（用于后续检索）

## 输出格式

请严格按照以下 JSON 格式输出：

```json
{{
    "problem_summary": "简洁描述核心问题（一句话）",
    "solution_summary": "简洁描述解决方案（一句话）",
    "lesson": "可复用的经验教训（2-3句话）",
    "scope": "universal 或 project_specific",
    "scope_reason": "分类理由（一句话）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "confidence": 0.9
}}
```

注意：
- 只输出 JSON，不要有其他内容
- confidence 表示你对这个分析的置信度（0-1）
- 如果问题太模糊或记录不完整，confidence 应该较低
"""


class ExperienceRefiner:
    """使用 LLM 精炼原始经验"""
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: LLM 客户端，需要有 generate(prompt) 方法
        """
        self._llm = llm_client
    
    def set_llm(self, llm_client):
        """设置 LLM 客户端"""
        self._llm = llm_client
    
    def refine(self, raw_experience: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        精炼单个原始经验
        
        Args:
            raw_experience: {id, content, metadata}
            
        Returns:
            精炼后的经验 {id, content, metadata} 或 None
        """
        if self._llm is None:
            logger.error("LLM client not set")
            return None
        
        raw_content = raw_experience.get("content", "")
        if not raw_content:
            return None
        
        prompt = REFINE_PROMPT.format(raw_content=raw_content)
        
        try:
            response = self._llm.generate(prompt)
            result = self._parse_response(response)
            
            if not result:
                logger.warning(f"Failed to parse LLM response for {raw_experience.get('id')}")
                return None
            
            # 构建精炼后的经验
            refined_content = self._build_refined_content(result, raw_experience)
            refined_metadata = self._build_refined_metadata(result, raw_experience)
            
            return {
                "id": raw_experience.get("id"),
                "content": refined_content,
                "metadata": refined_metadata
            }
            
        except Exception as e:
            logger.error(f"Error refining experience {raw_experience.get('id')}: {e}")
            return None
    
    def refine_batch(self, raw_experiences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量精炼经验"""
        refined = []
        for exp in raw_experiences:
            result = self.refine(exp)
            if result:
                refined.append(result)
        return refined
    
    def _parse_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 响应"""
        if not response:
            return None
        
        # 尝试提取 JSON
        response = response.strip()
        
        # 移除可能的 markdown 代码块标记
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        try:
            result = json.loads(response)
            
            # 验证必要字段
            required_fields = ["problem_summary", "solution_summary", "lesson", "scope", "keywords"]
            if not all(f in result for f in required_fields):
                logger.warning(f"Missing required fields in LLM response")
                return None
            
            # 验证 scope 值
            if result["scope"] not in ["universal", "project_specific"]:
                result["scope"] = "project_specific"  # 默认保守处理
            
            return result
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}")
            return None
    
    def _build_refined_content(
        self,
        result: Dict[str, Any],
        raw: Dict[str, Any]
    ) -> str:
        """构建用于嵌入的内容"""
        parts = []
        
        # 问题和解决方案
        parts.append(f"Problem: {result['problem_summary']}")
        parts.append(f"Solution: {result['solution_summary']}")
        parts.append(f"Lesson: {result['lesson']}")
        
        # 关键词
        keywords = result.get("keywords", [])
        if keywords:
            parts.append(f"Keywords: {', '.join(keywords)}")
        
        # 项目类型
        project_type = raw.get("metadata", {}).get("project_type", "unknown")
        framework = raw.get("metadata", {}).get("framework", "")
        if framework:
            parts.append(f"Framework: {framework}")
        parts.append(f"Project Type: {project_type}")
        
        return "\n".join(parts)
    
    def _build_refined_metadata(
        self,
        result: Dict[str, Any],
        raw: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建元数据"""
        raw_meta = raw.get("metadata", {})
        
        return {
            "raw_id": raw.get("id"),
            "scope": result["scope"],
            "scope_reason": result.get("scope_reason", ""),
            "confidence": result.get("confidence", 0.5),
            "problem_summary": result["problem_summary"],
            "solution_summary": result["solution_summary"],
            "lesson": result["lesson"],
            "keywords": ",".join(result.get("keywords", [])),
            "project_type": raw_meta.get("project_type", "unknown"),
            "framework": raw_meta.get("framework", ""),
            "source_log": raw_meta.get("source_log", ""),
        }
    
    def extract_for_prompt(self, refined: Dict[str, Any]) -> str:
        """
        将精炼经验格式化为适合注入 prompt 的格式
        """
        meta = refined.get("metadata", {})
        
        lines = [
            f"[{meta.get('scope', 'unknown').upper()}] {meta.get('problem_summary', 'Unknown problem')}",
            f"  Solution: {meta.get('solution_summary', 'Unknown solution')}",
            f"  Lesson: {meta.get('lesson', '')}",
        ]
        
        framework = meta.get("framework")
        if framework:
            lines.append(f"  Framework: {framework}")
        
        return "\n".join(lines)
