"""Chain of Thought (CoT) Framework for Deep Reasoning.

This module provides a tiered reasoning framework that adapts to task complexity,
minimizing token usage while maintaining decision quality.
"""

# ============================================================================
# Core Chain of Thought Principles (Lightweight)
# ============================================================================

CORE_COT_PRINCIPLES = """
# 🧠 思维链原则

做决策前遵循：观察 → 分析 → 决策 → 验证

**两级推理系统：**

**正常模式（简化推理）：**
- 常规命令执行（git clone, npm install等）
- 明确的下一步操作
- 前一步成功后的后续操作
- 使用格式：why + verify

**错误/决策模式（复杂推理）：**
- 遇到错误或失败时
- 需要多方案选择
- 用户交互需要解释
- 不确定最佳路径
- 使用格式：observation + analysis + options + chosen + why

**反模式（避免）：**
- ❌ 不检查状态就决策
- ❌ 失败后重复相同操作而不分析原因
- ❌ 忽略约束条件
- ❌ 没有验证计划
"""

# ============================================================================
# Two-Level Reasoning System
# ============================================================================

# Level 1: Simple Reasoning (for normal operations - 80% of cases)
SIMPLE_REASONING_FORMAT = """
## 简化推理格式（正常模式）

```json
{
  "action": "execute",
  "command": "npm install",
  "reasoning": {
    "why": "package.json存在但node_modules缺失，需要安装依赖",
    "verify": "检查node_modules/目录存在"
  }
}
```

适用场景：
- 标准命令执行（git clone, npm install, pip install）
- 明确的下一步操作
- 常规部署流程
- 前一步成功后的后续操作
"""

# Level 2: Complex Reasoning (for errors and difficult decisions - 20% of cases)
COMPLEX_REASONING_FORMAT = """
## 复杂推理格式（错误/决策模式）

```json
{
  "action": "ask_user",
  "question": "端口3000被占用，如何处理？",
  "options": ["杀掉占用进程", "使用端口3001", "使用端口8080"],
  "reasoning": {
    "observation": "端口3000被占用，应用启动失败",
    "analysis": "需要选择可用端口，但不知用户偏好",
    "options": [
      "A: 杀掉进程（风险：可能影响其他服务）",
      "B: 使用3001（安全但非默认）",
      "C: 询问用户（最佳：让用户决定）"
    ],
    "chosen": "C - 询问用户",
    "why": "端口冲突决策应由用户控制，避免破坏性操作"
  }
}
```

适用场景：
- 遇到错误或失败需要诊断
- 多个方案需要权衡利弊
- 风险操作需要决策
- 需要向用户解释原因
- 不确定最佳路径时
"""

# ============================================================================
# Error Analysis Framework (Streamlined)
# ============================================================================

ERROR_ANALYSIS_FRAMEWORK = """
# 🔍 错误分析框架

遇到命令失败时：

## 1. 提取关键信息
- Exit code: 是什么？
- 最具体的错误消息（不是通用包装错误）
- 提到的文件路径/服务名/端口

## 2. 识别根本原因
错误链：通用错误 → 中间错误 → **根本原因**（最具体）

常见模式：
- "Cannot connect" + 文件/socket路径 → 服务未启动
- "EADDRINUSE" + 端口号 → 端口被占用
- "permission denied" + 路径 → 权限问题
- "command/module not found" + 名称 → 未安装

## 3. 选择解决方案
优先级：
1. 检查状态（验证假设）
2. 修复根本原因（不是重试相同命令）
3. 如果不确定，询问用户

## 4. 平台差异
- Linux: systemctl, /var/run/, sudo
- Windows: Get-Service, 命名管道 (//./pipe/*), 执行策略
"""

# ============================================================================
# User Interaction Guidelines (Condensed)
# ============================================================================

USER_INTERACTION_GUIDE = """
# 💬 用户交互指南

**何时询问：**
- 多个部署选项（端口、模式、环境变量）
- 缺少信息无法继续
- 风险操作需要确认
- 错误恢复需要指导

**如何询问：**
```json
{
  "action": "ask_user",
  "question": "清晰的问题",
  "options": ["选项1", "选项2", "选项3"],
  "input_type": "choice",  // choice/text/confirm/secret
  "category": "decision",   // decision/confirmation/information/error_recovery
  "reasoning": "为什么需要用户输入"
}
```
"""

# ============================================================================
# Planning Phase Template (Simplified)
# ============================================================================

PLANNING_PHASE_GUIDE = """
# 📋 规划阶段指南

分析项目并生成部署计划：

1. **项目理解**：类型、技术栈、依赖
2. **环境分析**：操作系统、已安装工具、约束
3. **策略选择**：Docker vs 传统部署
4. **步骤设计**：先决条件 → 设置 → 构建 → 部署 → 验证
5. **风险识别**：可能的问题和缓解措施

输出：结构化JSON计划
"""

# ============================================================================
# Execution Phase Template (Simplified)
# ============================================================================

EXECUTION_PHASE_GUIDE = """
# ⚡ 执行阶段指南

每个步骤：
1. **执行前**：观察状态，明确目标
2. **执行**：使用适当的推理模式
3. **执行后**：验证结果，检查成功标准
4. **失败时**：切换到复杂推理模式，分析错误，不要重复相同失败的命令

使用两级推理：
- 正常模式 → 简化格式（why + verify）
- 遇到错误或决策 → 复杂格式（observation + analysis + options + chosen + why）

**重要**：一旦遇到错误，立即切换到复杂推理模式进行详细分析。
"""

# ============================================================================
# Helper Functions
# ============================================================================

def get_cot_framework(
    phase: str = "execution",
    complexity: str = "adaptive"
) -> str:
    """Get the appropriate Chain of Thought framework.

    Args:
        phase: "planning" or "execution"
        complexity: "simple", "complex", or "adaptive" (default)

    Returns:
        Formatted CoT framework string
    """
    # Base principles (always included)
    base = CORE_COT_PRINCIPLES

    # Phase-specific guidance
    if phase == "planning":
        phase_guide = PLANNING_PHASE_GUIDE
    else:
        phase_guide = EXECUTION_PHASE_GUIDE

    # Complexity-specific format
    if complexity == "simple":
        reasoning_format = SIMPLE_REASONING_FORMAT
    elif complexity == "complex":
        reasoning_format = COMPLEX_REASONING_FORMAT
    else:  # adaptive - include both levels
        reasoning_format = f"{SIMPLE_REASONING_FORMAT}\n\n{COMPLEX_REASONING_FORMAT}"

    # Combine
    parts = [
        base,
        "\n" + "="*70 + "\n",
        phase_guide,
        "\n" + "="*70 + "\n",
        reasoning_format,
        "\n" + "="*70 + "\n",
        ERROR_ANALYSIS_FRAMEWORK,
        "\n" + "="*70 + "\n",
        USER_INTERACTION_GUIDE
    ]

    return "\n".join(parts)


def get_reasoning_requirements(detailed: bool = False) -> str:
    """Get reasoning output requirements.

    Args:
        detailed: If True, allow complex reasoning. If False, prefer simple reasoning.

    Returns:
        Requirements string for reasoning output
    """
    if detailed:
        return """
## Reasoning要求

根据情况选择合适的推理模式：

**正常模式**（常规操作）：
```json
"reasoning": {
  "why": "为什么执行这个命令",
  "verify": "如何验证成功"
}
```

**错误/决策模式**（遇到错误或需要决策时）：
```json
"reasoning": {
  "observation": "详细状态",
  "analysis": "分析",
  "options": ["方案A", "方案B"],
  "chosen": "选择的方案",
  "why": "选择原因"
}
```

**原则**：正常操作使用简化推理，遇到错误或需要决策时使用复杂推理。
"""
    else:
        return """
## Reasoning要求

使用简化推理格式：
```json
"reasoning": {
  "why": "为什么这样做",
  "verify": "如何验证"
}
```

仅在遇到错误或需要决策时切换到复杂推理模式。
"""


def get_simple_cot() -> str:
    """Get minimal CoT framework for simple tasks.
    
    Returns:
        Minimal CoT framework
    """
    return f"{CORE_COT_PRINCIPLES}\n\n{SIMPLE_REASONING_FORMAT}\n\n{ERROR_ANALYSIS_FRAMEWORK}"


def get_standard_cot() -> str:
    """Get complex CoT framework for errors and decisions.

    Returns:
        Complex CoT framework
    """
    return f"{CORE_COT_PRINCIPLES}\n\n{COMPLEX_REASONING_FORMAT}\n\n{ERROR_ANALYSIS_FRAMEWORK}\n\n{USER_INTERACTION_GUIDE}"


def get_full_cot() -> str:
    """Get complete CoT framework with both reasoning levels.

    Returns:
        Full CoT framework (adaptive mode)
    """
    return get_cot_framework(complexity="adaptive")


# ============================================================================
# Backwards Compatibility Exports
# ============================================================================

# For code that still references old names
CHAIN_OF_THOUGHT_FRAMEWORK = CORE_COT_PRINCIPLES
PLANNING_COT_TEMPLATE = PLANNING_PHASE_GUIDE
EXECUTION_COT_TEMPLATE = EXECUTION_PHASE_GUIDE
REASONING_OUTPUT_FORMAT = f"{SIMPLE_REASONING_FORMAT}\n\n{COMPLEX_REASONING_FORMAT}"

# Legacy compatibility - map old names to new
STANDARD_REASONING_FORMAT = COMPLEX_REASONING_FORMAT  # Map to complex reasoning
FULL_REASONING_FORMAT = COMPLEX_REASONING_FORMAT     # Map to complex reasoning

# Deprecated - use ERROR_ANALYSIS_FRAMEWORK instead
ERROR_ANALYSIS_COT = ERROR_ANALYSIS_FRAMEWORK

# Deprecated - simplified into USER_INTERACTION_GUIDE
USER_FEEDBACK_COT = """
# 💬 用户反馈处理

用户反馈时：
1. 理解反馈内容和上下文
2. 分类：回答/指令/纠正/求助
3. 提取可执行项
4. 立即采取行动

避免：重复询问相同问题，忽略明确指令。
"""
