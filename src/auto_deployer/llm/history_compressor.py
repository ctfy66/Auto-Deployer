"""Command history compression using LLM.

This module provides intelligent compression of command execution history
to reduce token usage while preserving critical information.
"""

from __future__ import annotations

import logging
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseLLMProvider
    from ..orchestrator.models import CommandRecord

logger = logging.getLogger(__name__)

COMPRESSION_SYSTEM_PROMPT = """You are a command execution history compressor for deployment automation.

Your task: Compress a list of shell command executions into a concise, factual summary.

Input format:
- Command: {shell command}
- Success: {true/false}
- Exit Code: {number}
- Output: {stdout/stderr}

Output format:
Use plain text with clear sections. Group related commands logically (e.g., "Environment Check", "Dependency Installation").

For each command or group:
- Command → Result summary
- For success: Brief output (key info only)
- For failure: Error message and exit code

Rules:
1. Be factual - record what happened, not analysis
2. Group related commands under section headers
3. Keep successful commands brief (one line)
4. Keep error details for failed commands
5. Preserve key outputs (versions, paths, ports, PIDs)
6. Remove duplicate/redundant information
7. Use arrow notation: command → result

Example:
```
Environment Check:
  which python3 → /usr/bin/python3
  python3 --version → Python 3.11.4

Setup:
  mkdir -p ~/app → Success
  cd ~/app → Success
  
Install Failed:
  pip install -r requirements.txt → FAILED (exit 1)
  Error: Could not find package 'nonexistent-package'
```

Compress the following command history:"""


class HistoryCompressor:
    """Compresses command execution history using LLM."""
    
    def __init__(self, llm_provider: "BaseLLMProvider"):
        """
        Initialize history compressor.
        
        Args:
            llm_provider: LLM provider instance to use for compression
        """
        self.llm_provider = llm_provider
        logger.debug("HistoryCompressor initialized")
    
    def compress(
        self,
        commands: List["CommandRecord"],
        step_name: str,
        step_goal: str,
    ) -> str:
        """
        Compress a list of command records into a concise summary.
        
        Args:
            commands: List of CommandRecord objects to compress
            step_name: Name of the step (for context)
            step_goal: Goal of the step (for context)
            
        Returns:
            Compressed history as plain text string
        """
        if not commands:
            return "(no commands to compress)"
        
        logger.info(f"Compressing {len(commands)} commands for step: {step_name}")
        
        # Build compression prompt
        prompt = self._build_compression_prompt(commands, step_name, step_goal)
        
        try:
            # Call LLM for compression
            compressed_text = self.llm_provider.generate_response(
                prompt=prompt,
                system_prompt=COMPRESSION_SYSTEM_PROMPT,
                response_format="text",  # Plain text, not JSON
                timeout=30,
                max_retries=2,
            )
            
            if not compressed_text:
                logger.error("LLM returned empty response for compression")
                return self._fallback_compression(commands)
            
            logger.info(f"Compression successful: {len(commands)} commands → {len(compressed_text)} chars")
            return compressed_text.strip()
            
        except Exception as e:
            logger.error(f"Compression failed: {e}, using fallback")
            return self._fallback_compression(commands)
    
    def _build_compression_prompt(
        self,
        commands: List["CommandRecord"],
        step_name: str,
        step_goal: str,
    ) -> str:
        """Build the compression prompt from command records."""
        command_list = []
        
        for i, cmd in enumerate(commands, 1):
            status = "Success" if cmd.success else f"FAILED (exit {cmd.exit_code})"
            
            # Truncate outputs for compression prompt (LLM doesn't need full details)
            stdout_preview = cmd.stdout[:500] if cmd.stdout else "(no output)"
            stderr_preview = cmd.stderr[:300] if cmd.stderr else "(no errors)"
            
            command_list.append(f"""
Command {i}:
  Command: {cmd.command}
  Status: {status}
  Output: {stdout_preview}
  Error: {stderr_preview}
""")
        
        return f"""Step: {step_name}
Goal: {step_goal}

Commands to compress:
{''.join(command_list)}

Provide the compressed history in plain text format (do not use markdown code blocks):"""
    
    def _fallback_compression(self, commands: List["CommandRecord"]) -> str:
        """
        Fallback compression method if LLM fails.
        
        Uses simple rule-based compression.
        """
        lines = ["=== Compressed History (Fallback) ==="]
        
        for i, cmd in enumerate(commands, 1):
            if cmd.success:
                # For successful commands, just show command and brief result
                lines.append(f"{i}. {cmd.command} → Success")
                # Include first line of output if informative
                if cmd.stdout:
                    first_line = cmd.stdout.split('\n')[0][:100]
                    if first_line and not first_line.isspace():
                        lines.append(f"   Output: {first_line}")
            else:
                # For failed commands, show more detail
                lines.append(f"{i}. {cmd.command} → FAILED (exit {cmd.exit_code})")
                if cmd.stderr:
                    # Show first error line
                    first_error = cmd.stderr.split('\n')[0][:200]
                    lines.append(f"   Error: {first_error}")
        
        return "\n".join(lines)
