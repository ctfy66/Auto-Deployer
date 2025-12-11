"""
智能命令输出提取器
根据命令执行结果，提取关键信息而非简单截断
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ExtractedOutput:
    """提取后的输出"""
    summary: str  # 一句话总结
    key_info: List[str]  # 关键信息列表
    error_context: Optional[str] = None  # 错误上下文（失败时）
    full_length: int = 0  # 原始输出长度
    extracted_length: int = 0  # 提取后长度


class CommandOutputExtractor:
    """命令输出智能提取器"""

    # 关键信息模式（成功时提取）
    KEY_PATTERNS = {
        'port': r'(?:port|端口)[:：\s]+(\d+)',
        'pid': r'(?:pid|process id|进程ID)[:：\s]+(\d+)',
        'url': r'https?://[^\s]+',
        'ip': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        'path': r'/[/\w\-\.]+|[A-Z]:[/\\][\w\-\\/.]+',
        'version': r'v?\d+\.\d+\.\d+',
        'status': r'(?:status|状态)[:：\s]+(running|stopped|active|inactive|启动|停止)',
    }

    # 错误模式（失败时提取）
    ERROR_PATTERNS = {
        'error_line': r'(?i)error[:：\s].*',
        'exception': r'(?i)(?:exception|traceback).*',
        'failed': r'(?i)failed[:：\s].*',
        'fatal': r'(?i)fatal[:：\s].*',
        'cannot': r'(?i)cannot.*',
        'permission': r'(?i)permission denied.*',
        'not_found': r'(?i)(?:not found|找不到|无法找到).*',
        'timeout': r'(?i)timeout.*',
        'connection': r'(?i)connection (?:refused|reset|closed).*',
    }

    # 噪音模式（始终过滤）
    NOISE_PATTERNS = [
        r'^\s*$',  # 空行
        r'^[\-=]{3,}$',  # 分隔线
        r'(?i)^debug[:：\s]',  # Debug日志
        r'(?i)^trace[:：\s]',  # Trace日志
        r'^[\d\-:T\.]+\s+(?:DEBUG|TRACE)',  # 时间戳+DEBUG
    ]

    def __init__(self, max_success_lines: int = 50, max_error_lines: int = 100):
        """
        初始化提取器

        Args:
            max_success_lines: 成功时最大保留行数
            max_error_lines: 失败时最大保留行数
        """
        self.max_success_lines = max_success_lines
        self.max_error_lines = max_error_lines

    def extract(
        self,
        stdout: str,
        stderr: str,
        success: bool,
        exit_code: int,
        command: str = ""
    ) -> ExtractedOutput:
        """
        智能提取命令输出

        Args:
            stdout: 标准输出
            stderr: 错误输出
            success: 是否成功
            exit_code: 退出码
            command: 执行的命令（用于上下文理解）

        Returns:
            ExtractedOutput: 提取后的结构化输出
        """
        full_output = f"{stdout}\n{stderr}".strip()
        full_length = len(full_output)

        if success:
            return self._extract_success_output(stdout, stderr, command, full_length)
        else:
            return self._extract_error_output(stdout, stderr, exit_code, command, full_length)

    def _extract_success_output(
        self,
        stdout: str,
        stderr: str,
        command: str,
        full_length: int
    ) -> ExtractedOutput:
        """提取成功时的关键信息"""
        key_info = []

        # 1. 提取关键模式匹配
        combined_output = f"{stdout}\n{stderr}"
        for info_type, pattern in self.KEY_PATTERNS.items():
            matches = re.findall(pattern, combined_output, re.IGNORECASE)
            if matches:
                # 去重
                unique_matches = list(set(matches))[:3]  # 最多保留3个同类
                for match in unique_matches:
                    key_info.append(f"{info_type}: {match}")

        # 2. 提取包含关键词的行
        success_keywords = [
            'successfully', 'success', 'completed', 'done', 'started', 'running',
            '成功', '完成', '启动', '运行中'
        ]
        lines = combined_output.split('\n')
        for line in lines:
            line_stripped = line.strip()
            if any(kw in line_stripped.lower() for kw in success_keywords):
                if len(line_stripped) < 200:  # 避免超长行
                    key_info.append(line_stripped)
                if len(key_info) >= self.max_success_lines:
                    break

        # 3. 如果没有提取到任何信息，保留最后几行
        if not key_info:
            last_lines = [l.strip() for l in lines[-5:] if l.strip()]
            key_info = last_lines

        # 4. 生成总结
        summary = self._generate_success_summary(command, key_info)

        extracted_text = "\n".join(key_info)
        return ExtractedOutput(
            summary=summary,
            key_info=key_info,
            error_context=None,
            full_length=full_length,
            extracted_length=len(extracted_text)
        )

    def _extract_error_output(
        self,
        stdout: str,
        stderr: str,
        exit_code: int,
        command: str,
        full_length: int
    ) -> ExtractedOutput:
        """提取失败时的错误上下文"""
        error_lines = []

        # 1. 优先处理stderr
        if stderr:
            error_lines.extend(self._extract_error_lines(stderr))

        # 2. 如果stderr没有错误信息，检查stdout
        if not error_lines and stdout:
            error_lines.extend(self._extract_error_lines(stdout))

        # 3. 提取错误类型
        error_type = self._identify_error_type(f"{stdout}\n{stderr}")

        # 4. 限制行数
        if len(error_lines) > self.max_error_lines:
            # 保留最相关的错误行
            error_lines = error_lines[:self.max_error_lines]

        # 5. 生成总结
        summary = self._generate_error_summary(command, exit_code, error_type, error_lines)

        # 6. 构建错误上下文
        error_context = "\n".join(error_lines) if error_lines else stderr[:500]

        return ExtractedOutput(
            summary=summary,
            key_info=[f"Exit code: {exit_code}", f"Error type: {error_type}"],
            error_context=error_context,
            full_length=full_length,
            extracted_length=len(error_context)
        )

    def _extract_error_lines(self, text: str) -> List[str]:
        """从文本中提取错误相关行"""
        lines = text.split('\n')
        error_lines = []

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # 跳过噪音行
            if self._is_noise(line_stripped):
                continue

            # 检查是否匹配错误模式
            is_error_line = False
            for pattern in self.ERROR_PATTERNS.values():
                if re.search(pattern, line_stripped):
                    is_error_line = True
                    break

            if is_error_line:
                # 添加错误行及其上下文（前1行，后2行）
                context_start = max(0, i - 1)
                context_end = min(len(lines), i + 3)
                context_lines = lines[context_start:context_end]

                for ctx_line in context_lines:
                    ctx_stripped = ctx_line.strip()
                    if ctx_stripped and not self._is_noise(ctx_stripped):
                        if ctx_stripped not in error_lines:  # 去重
                            error_lines.append(ctx_stripped)

        # 如果没有匹配到错误模式，返回最后几行
        if not error_lines:
            error_lines = [l.strip() for l in lines[-10:] if l.strip() and not self._is_noise(l.strip())]

        return error_lines

    def _is_noise(self, line: str) -> bool:
        """判断是否为噪音行"""
        for pattern in self.NOISE_PATTERNS:
            if re.match(pattern, line):
                return True
        return False

    def _identify_error_type(self, text: str) -> str:
        """识别错误类型"""
        text_lower = text.lower()

        if 'permission denied' in text_lower or 'access denied' in text_lower:
            return "Permission Error"
        elif 'not found' in text_lower or '找不到' in text_lower:
            return "Not Found Error"
        elif 'timeout' in text_lower:
            return "Timeout Error"
        elif 'connection refused' in text_lower or 'connection reset' in text_lower:
            return "Connection Error"
        elif 'syntax error' in text_lower:
            return "Syntax Error"
        elif 'out of memory' in text_lower or 'oom' in text_lower:
            return "Memory Error"
        elif 'disk' in text_lower and ('full' in text_lower or 'space' in text_lower):
            return "Disk Space Error"
        elif 'port' in text_lower and 'already in use' in text_lower:
            return "Port Conflict Error"
        else:
            return "Unknown Error"

    def _generate_success_summary(self, command: str, key_info: List[str]) -> str:
        """生成成功总结"""
        cmd_short = command[:50] + "..." if len(command) > 50 else command

        if not key_info:
            return f"✓ Command succeeded: {cmd_short}"

        # 尝试提取最关键的信息
        info_str = ", ".join(key_info[:3])
        if len(info_str) > 100:
            info_str = info_str[:100] + "..."

        return f"✓ Command succeeded: {cmd_short} | {info_str}"

    def _generate_error_summary(
        self,
        command: str,
        exit_code: int,
        error_type: str,
        error_lines: List[str]
    ) -> str:
        """生成错误总结"""
        cmd_short = command[:50] + "..." if len(command) > 50 else command

        # 提取第一行错误消息
        first_error = error_lines[0] if error_lines else "No error details"
        if len(first_error) > 80:
            first_error = first_error[:80] + "..."

        return f"✗ Command failed (exit {exit_code}): {cmd_short} | {error_type}: {first_error}"

    def format_for_llm(self, extracted: ExtractedOutput) -> str:
        """
        格式化为适合LLM的字符串

        Returns:
            格式化后的字符串，供prompt使用
        """
        parts = [extracted.summary]

        if extracted.key_info:
            parts.append("Key Info:")
            parts.extend([f"  - {info}" for info in extracted.key_info[:10]])

        if extracted.error_context:
            parts.append("Error Details:")
            # 限制错误上下文长度
            error_preview = extracted.error_context[:800]
            if len(extracted.error_context) > 800:
                error_preview += f"\n... ({len(extracted.error_context) - 800} more chars)"
            parts.append(error_preview)

        # 添加压缩比信息
        if extracted.full_length > 0:
            ratio = (1 - extracted.extracted_length / extracted.full_length) * 100
            parts.append(f"[Compressed: {extracted.full_length}→{extracted.extracted_length} chars, {ratio:.1f}% saved]")

        return "\n".join(parts)


# 便捷函数
def extract_output(
    stdout: str,
    stderr: str,
    success: bool,
    exit_code: int,
    command: str = "",
    max_success_lines: int = 50,
    max_error_lines: int = 100
) -> str:
    """
    快速提取命令输出的便捷函数

    Returns:
        格式化后的字符串，可直接用于LLM prompt
    """
    extractor = CommandOutputExtractor(max_success_lines, max_error_lines)
    extracted = extractor.extract(stdout, stderr, success, exit_code, command)
    return extractor.format_for_llm(extracted)
