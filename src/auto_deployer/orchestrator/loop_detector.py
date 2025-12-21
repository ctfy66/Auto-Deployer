"""Loop detection for deployment step execution.

This module provides loop detection capabilities to identify when the agent
is stuck in repetitive patterns without making progress.
"""

from __future__ import annotations

import re
import logging
from typing import List, TYPE_CHECKING
from difflib import SequenceMatcher

from .models import LoopDetectionResult, CommandRecord

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class LoopDetector:
    """循环检测器
    
    检测Agent是否陷入重复执行相似命令的循环，基于：
    1. 命令文本相似度
    2. 输出内容相似度
    3. 错误消息重复模式
    """
    
    def __init__(
        self,
        enabled: bool = True,
        direct_repeat_threshold: int = 3,
        error_loop_threshold: int = 4,
        command_similarity_threshold: float = 0.85,
        output_similarity_threshold: float = 0.80,
    ):
        """初始化循环检测器
        
        Args:
            enabled: 是否启用循环检测
            direct_repeat_threshold: 直接重复触发阈值（连续相同命令次数）
            error_loop_threshold: 错误循环触发阈值（连续失败次数）
            command_similarity_threshold: 命令相似度阈值（0-1）
            output_similarity_threshold: 输出相似度阈值（0-1）
        """
        self.enabled = enabled
        self.direct_repeat_threshold = direct_repeat_threshold
        self.error_loop_threshold = error_loop_threshold
        self.cmd_sim_threshold = command_similarity_threshold
        self.out_sim_threshold = output_similarity_threshold
        
        logger.info(f"LoopDetector initialized (enabled={enabled})")
    
    def check(self, commands: List[CommandRecord]) -> LoopDetectionResult:
        """检测是否存在循环
        
        Args:
            commands: 命令执行历史记录
            
        Returns:
            LoopDetectionResult: 检测结果
        """
        if not self.enabled or len(commands) < 3:
            return LoopDetectionResult(
                is_loop=False, 
                loop_type="none", 
                confidence=0.0, 
                evidence=[],
                loop_commands_indices=[]
            )
        
        # 1. 检测直接重复（优先级最高）
        result = self._check_direct_repeat(commands)
        if result.is_loop:
            return result
        
        # 2. 检测错误循环
        result = self._check_error_loop(commands)
        if result.is_loop:
            return result
        
        return LoopDetectionResult(
            is_loop=False,
            loop_type="none",
            confidence=0.0,
            evidence=[],
            loop_commands_indices=[]
        )
    
    def _check_direct_repeat(self, commands: List[CommandRecord]) -> LoopDetectionResult:
        """检测直接重复：AAA模式
        
        当连续N次执行相似命令且输出相似时，判定为循环
        """
        n = self.direct_repeat_threshold
        if len(commands) < n:
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        recent = commands[-n:]
        indices = list(range(len(commands) - n, len(commands)))
        
        # 计算命令相似度
        cmd_similarities = []
        for i in range(1, len(recent)):
            sim = self._command_similarity(recent[0].command, recent[i].command)
            cmd_similarities.append(sim)
        
        if not cmd_similarities:
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        avg_cmd_sim = sum(cmd_similarities) / len(cmd_similarities)
        
        if avg_cmd_sim < self.cmd_sim_threshold:
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        # 计算输出相似度
        out_similarities = []
        for i in range(1, len(recent)):
            output0 = recent[0].stdout + recent[0].stderr
            output_i = recent[i].stdout + recent[i].stderr
            sim = self._output_similarity(output0, output_i)
            out_similarities.append(sim)
        
        avg_out_sim = sum(out_similarities) / len(out_similarities) if out_similarities else 0.0
        
        if avg_out_sim < self.out_sim_threshold:
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        # 确认循环
        cmd_preview = recent[0].command[:60] + "..." if len(recent[0].command) > 60 else recent[0].command
        evidence = [
            f"Command repeated {n} times: {cmd_preview}",
            f"Avg command similarity: {avg_cmd_sim:.2f}",
            f"Avg output similarity: {avg_out_sim:.2f}"
        ]
        
        confidence = min(avg_cmd_sim, avg_out_sim + 0.1)
        
        logger.warning(f"Direct repeat loop detected: {evidence[0]}")
        
        return LoopDetectionResult(
            is_loop=True,
            loop_type="direct_repeat",
            confidence=confidence,
            evidence=evidence,
            loop_commands_indices=indices
        )
    
    def _check_error_loop(self, commands: List[CommandRecord]) -> LoopDetectionResult:
        """检测错误循环：不同命令但相同错误
        
        当多个不同的命令持续失败，且错误消息相似时，判定为循环
        """
        n = self.error_loop_threshold
        if len(commands) < n:
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        recent = commands[-n:]
        
        # 只关注失败的命令
        failed = [(i, cmd) for i, cmd in enumerate(recent) if cmd.exit_code != 0]
        
        if len(failed) < n * 0.75:  # 至少75%失败
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        # 提取错误特征
        error_sigs = [self._extract_error_signature(cmd.stderr) for _, cmd in failed]
        
        # 检查错误相似度
        similarities = []
        for i in range(1, len(error_sigs)):
            sim = self._text_similarity(error_sigs[0], error_sigs[i])
            similarities.append(sim)
        
        if not similarities:
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        avg_error_sim = sum(similarities) / len(similarities)
        
        if avg_error_sim < 0.75:
            return LoopDetectionResult(False, "none", 0.0, [], [])
        
        indices = [len(commands) - n + i for i, _ in failed]
        error_preview = error_sigs[0][:80] + "..." if len(error_sigs[0]) > 80 else error_sigs[0]
        evidence = [
            f"Continuous failures: {len(failed)}/{n} commands",
            f"Repeated error: {error_preview}",
            f"Error similarity: {avg_error_sim:.2f}"
        ]
        
        logger.warning(f"Error loop detected: {evidence[1]}")
        
        return LoopDetectionResult(
            is_loop=True,
            loop_type="error_loop",
            confidence=avg_error_sim,
            evidence=evidence,
            loop_commands_indices=indices
        )
    
    # ===== 辅助方法 =====
    
    def _command_similarity(self, cmd1: str, cmd2: str) -> float:
        """计算两个命令的相似度 (0-1)"""
        c1 = ' '.join(cmd1.lower().split())
        c2 = ' '.join(cmd2.lower().split())
        return SequenceMatcher(None, c1, c2).ratio()
    
    def _output_similarity(self, out1: str, out2: str) -> float:
        """计算两个输出的相似度 (0-1)"""
        o1 = self._normalize_output(out1)
        o2 = self._normalize_output(out2)
        
        # 对长文本采样（取首尾）
        if len(o1) > 2000:
            o1 = o1[:1000] + o1[-1000:]
        if len(o2) > 2000:
            o2 = o2[:1000] + o2[-1000:]
        
        return SequenceMatcher(None, o1, o2).ratio()
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """计算通用文本相似度 (0-1)"""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _normalize_output(self, output: str) -> str:
        """归一化输出，去除动态内容
        
        去除时间戳、PID等会变化但不影响语义的内容
        """
        # 去除时间戳
        output = re.sub(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}', '[TS]', output)
        
        # 去除毫秒时间戳
        output = re.sub(r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}\.\d+', '[TS]', output)
        
        # 去除PID
        output = re.sub(r'\b(pid|process)[:\s]+\d+', r'\1:[N]', output, flags=re.IGNORECASE)
        
        # 去除临时文件路径中的随机部分
        output = re.sub(r'/tmp/[\w\-]+', '/tmp/[TEMP]', output)
        output = re.sub(r'\\temp\\[\w\-]+', '\\temp\\[TEMP]', output, flags=re.IGNORECASE)
        
        # 统一空白字符
        output = ' '.join(output.split())
        
        return output.lower()
    
    def _extract_error_signature(self, stderr: str) -> str:
        """提取错误消息的特征签名
        
        提取错误消息中最具代表性的部分，用于比较
        """
        patterns = [
            r'Error:\s*(.{0,80})',
            r'Exception:\s*(.{0,80})',
            r'(EACCES|ENOENT|EPERM|EADDRINUSE|ECONNREFUSED)',
            r'(permission denied)',
            r'(command not found)',
            r'(cannot find module)',
            r'(port.*already in use)',
            r'(failed to|unable to|could not)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, stderr, re.IGNORECASE)
            if match:
                return match.group(0)
        
        # 如果没有匹配到特定模式，返回前100字符
        return stderr[:100].strip()
