"""Extract resolution chains from deployment logs."""

from __future__ import annotations

import json
import re
import hashlib
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import ResolutionChain, ResolutionStep, RawExperience

logger = logging.getLogger(__name__)


# 诊断类命令 - 不算真正的"解决方案"
DIAGNOSTIC_PATTERNS = [
    r'^ls\b',
    r'^cat\b',
    r'^echo\b',
    r'^pwd\b',
    r'^whoami\b',
    r'^head\b',
    r'^tail\b',
    r'^grep\b',
    r'^find\b',
    r'^which\b',
    r'^file\b',
    r'^stat\b',
    r'^test\b',
    r'^wc\b',
    r'\bstatus\b',           # systemctl status
    r'\b-v\s*$',             # version flag
    r'\b--version\b',
    r'^curl\s+.*-I\b',       # curl -I (header only)
    r'^curl\s+.*--head\b',
]

# 命令主题关键词，用于判断命令相关性
COMMAND_TOPICS = {
    "nginx": ["nginx", "sites-available", "sites-enabled", "/etc/nginx"],
    "npm": ["npm", "node_modules", "package.json", "package-lock"],
    "node": ["node", "nodejs", "nvm"],
    "pip": ["pip", "pip3", "requirements.txt", "venv", "virtualenv"],
    "python": ["python", "python3", "gunicorn", "uvicorn", "flask", "django"],
    "docker": ["docker", "container", "compose", "dockerfile"],
    "git": ["git clone", "git pull", "git checkout", "git fetch"],
    "apt": ["apt ", "apt-get", "dpkg", "apt-cache"],
    "systemctl": ["systemctl", "service ", "journalctl"],
    "sudo": ["sudo "],
    "file_ops": ["mkdir", "rm ", "cp ", "mv ", "chmod", "chown", "ln "],
}


def is_diagnostic_command(cmd: str) -> bool:
    """判断是否是诊断类命令"""
    if not cmd:
        return False
    cmd_lower = cmd.strip().lower()
    for pattern in DIAGNOSTIC_PATTERNS:
        if re.search(pattern, cmd_lower):
            return True
    return False


def get_command_topics(cmd: str) -> set:
    """提取命令的主题"""
    if not cmd:
        return set()
    
    cmd_lower = cmd.lower()
    topics = set()
    
    for topic, keywords in COMMAND_TOPICS.items():
        if any(kw in cmd_lower for kw in keywords):
            topics.add(topic)
    
    return topics


def is_related_command(cmd1: str, cmd2: str) -> bool:
    """判断两个命令是否相关"""
    topics1 = get_command_topics(cmd1)
    topics2 = get_command_topics(cmd2)
    
    # 有交集就算相关
    return bool(topics1 & topics2)


def is_resolution(
    failed_cmd: str,
    error_msg: str,
    success_cmd: str,
    success_reasoning: str
) -> bool:
    """判断成功命令是否真正解决了之前的失败"""
    
    # 1. 诊断命令不算解决
    if is_diagnostic_command(success_cmd):
        return False
    
    # 2. 命令相关性检查
    if is_related_command(failed_cmd, success_cmd):
        return True
    
    # 3. reasoning 中提到了修复
    reasoning_lower = (success_reasoning or "").lower()
    fix_indicators = [
        "fix", "resolve", "solution", "correct", "solved", "修复", "解决",
        "instead", "replace", "change", "modify", "update"
    ]
    if any(ind in reasoning_lower for ind in fix_indicators):
        # 还需要和原命令有一定关系
        if is_related_command(failed_cmd, success_cmd):
            return True
    
    return False


class ExperienceExtractor:
    """从部署日志中提取经验"""
    
    def __init__(self, log_dir: str = "agent_logs"):
        self.log_dir = Path(log_dir)
    
    def extract_from_log(self, log_path: Path) -> List[RawExperience]:
        """从单个日志文件提取经验"""
        try:
            with open(log_path, encoding="utf-8") as f:
                log = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read log {log_path}: {e}")
            return []
        
        # 只处理成功的部署
        if log.get("status") != "success":
            logger.debug(f"Skipping non-success log: {log_path}")
            return []
        
        steps = log.get("steps", [])
        context = log.get("context", {})
        
        chains = self._extract_resolution_chains(steps, context, str(log_path))
        
        experiences = []
        for chain in chains:
            exp = RawExperience(
                id=chain.id,
                chain=chain,
                content=chain.get_full_content(),
                project_type=chain.project_type,
                framework=chain.framework,
                source_log=str(log_path),
                timestamp=chain.timestamp,
                processed=False
            )
            experiences.append(exp)
        
        logger.info(f"Extracted {len(experiences)} experiences from {log_path.name}")
        return experiences
    
    def extract_from_all_logs(self) -> List[RawExperience]:
        """从所有日志文件提取经验"""
        all_experiences = []
        
        for log_path in sorted(self.log_dir.glob("deploy_*.json")):
            experiences = self.extract_from_log(log_path)
            all_experiences.extend(experiences)
        
        logger.info(f"Total extracted: {len(all_experiences)} experiences from {len(list(self.log_dir.glob('deploy_*.json')))} logs")
        return all_experiences
    
    def _extract_resolution_chains(
        self,
        steps: List[dict],
        context: dict,
        source_log: str
    ) -> List[ResolutionChain]:
        """提取所有问题修复链"""
        
        chains = []
        processed_indices = set()
        
        i = 0
        while i < len(steps):
            if i in processed_indices:
                i += 1
                continue
            
            step = steps[i]
            result = step.get("result", {})
            
            # result 可能是字符串（如 "SUCCESS"）或 dict
            if isinstance(result, str):
                # 字符串形式的 result，跳过
                i += 1
                continue
            
            # 找到一个失败的命令
            if not result.get("success", True):
                chain = self._extract_single_chain(steps, i, context, source_log)
                if chain:
                    chains.append(chain)
                    # 标记这个链中的所有步骤为已处理
                    for idx in range(chain.start_index, chain.end_index + 1):
                        processed_indices.add(idx)
                    i = chain.end_index + 1
                    continue
            
            i += 1
        
        return chains
    
    def _extract_single_chain(
        self,
        steps: List[dict],
        start_index: int,
        context: dict,
        source_log: str
    ) -> Optional[ResolutionChain]:
        """从某个失败点提取完整的修复链"""
        
        if start_index >= len(steps):
            return None
        
        failed_step = steps[start_index]
        failed_cmd = failed_step.get("command", "")
        failed_result = failed_step.get("result", {})
        
        # 处理 result 可能是字符串的情况
        if isinstance(failed_result, str):
            error_msg = ""
        else:
            error_msg = failed_result.get("stderr", "") or failed_result.get("stdout", "")
        
        chain_steps = []
        resolution_index = None
        
        # 添加初始失败步骤
        if isinstance(failed_result, str):
            stdout_val = ""
            stderr_val = ""
        else:
            stdout_val = failed_result.get("stdout", "")[:500]
            stderr_val = failed_result.get("stderr", "")[:500]
        
        chain_steps.append(ResolutionStep(
            index=start_index,
            command=failed_cmd,
            success=False,
            stdout=stdout_val,
            stderr=stderr_val,
            reasoning=failed_step.get("reasoning", ""),
            is_diagnostic=False
        ))
        
        # 往后找解决方案
        max_lookahead = min(start_index + 15, len(steps))  # 最多往后看15步
        
        for i in range(start_index + 1, max_lookahead):
            current = steps[i]
            current_cmd = current.get("command", "")
            current_result = current.get("result", {})
            
            # 处理 result 可能是字符串的情况
            if isinstance(current_result, str):
                current_success = current_result == "SUCCESS"
                current_stdout = ""
                current_stderr = ""
            else:
                current_success = current_result.get("success", False)
                current_stdout = current_result.get("stdout", "")[:500]
                current_stderr = current_result.get("stderr", "")[:500]
            
            current_reasoning = current.get("reasoning", "")
            
            is_diag = is_diagnostic_command(current_cmd)
            
            chain_steps.append(ResolutionStep(
                index=i,
                command=current_cmd,
                success=current_success,
                stdout=current_stdout,
                stderr=current_stderr,
                reasoning=current_reasoning,
                is_diagnostic=is_diag
            ))
            
            if current_success and not is_diag:
                # 检查是否真正解决了问题
                if is_resolution(failed_cmd, error_msg, current_cmd, current_reasoning):
                    resolution_index = i
                    break
                else:
                    # 可能是不相关的成功命令，继续往后看几步
                    # 但如果连续看到多个不相关的成功命令，就停止
                    unrelated_count = sum(
                        1 for s in chain_steps[-3:] 
                        if s.success and not s.is_diagnostic and not is_related_command(failed_cmd, s.command)
                    )
                    if unrelated_count >= 2:
                        # 移除不相关的步骤
                        chain_steps = chain_steps[:-unrelated_count]
                        break
        
        # 如果没找到解决方案，这个链无效
        if resolution_index is None:
            return None
        
        # 确保链至少有2步（失败 + 解决）
        if len(chain_steps) < 2:
            return None
        
        # 生成唯一ID
        chain_id = self._generate_chain_id(failed_cmd, error_msg, source_log)
        
        resolution_step = chain_steps[-1]
        
        return ResolutionChain(
            id=chain_id,
            start_index=start_index,
            end_index=resolution_index,
            steps=chain_steps,
            initial_command=failed_cmd,
            initial_error=error_msg[:500],
            resolution_command=resolution_step.command,
            resolution_reasoning=resolution_step.reasoning,
            project_type=context.get("project_type", "unknown"),
            framework=context.get("framework"),
            source_log=source_log,
            timestamp=datetime.now().isoformat()
        )
    
    def _generate_chain_id(self, cmd: str, error: str, source: str) -> str:
        """生成链的唯一ID"""
        content = f"{cmd}:{error[:100]}:{source}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
