# 失败案例学习机制设计

## 问题分析

### 现有机制的局限

当前 `extractor.py` 的 `_extract_single_chain()` 方法:

```python
# 如果没找到解决方案,这个链无效
if resolution_index is None:
    return None  # ❌ 失败案例被直接丢弃!
```

**无法学习的场景**:
1. ✗ 错误最终没有解决(用户放弃)
2. ✗ 需要用户手动干预(ask_user)
3. ✗ 步骤声明失败(step_failed)
4. ✗ 多次尝试但都失败
5. ✗ 诊断过程中发现的问题(没有修复)

**价值丢失**:
- 知道"什么方法不起作用"也是宝贵经验
- 知道"哪些错误需要人工介入"可以提前告警
- 知道"常见失败模式"可以避免重复尝试

## 解决方案:双轨学习机制

### 方案概述

同时提取两种类型的经验:
1. **ResolutionChain**(现有):失败 → 解决方案
2. **FailurePattern**(新增):失败 → 未解决/需人工

### 核心设计理念

**失败也是经验!** 学习内容:
- 哪些诊断方法尝试过但没效果
- 错误的严重程度(是否需要人工)
- 相似错误是否有成功案例

## 数据结构设计

### 1. FailurePattern 模型

```python
@dataclass
class FailurePattern:
    """记录未解决的失败模式"""

    # 唯一标识
    id: str

    # 失败信息
    initial_command: str
    initial_error: str
    error_summary: str  # LLM 生成的错误摘要

    # 尝试过的方法
    attempted_steps: List[ResolutionStep]  # 尝试过但失败的命令
    diagnostic_findings: List[str]  # 诊断过程中的发现

    # 结束原因
    termination_reason: str  # "max_iterations", "user_abort", "step_failed", "ask_user"
    termination_message: str  # 最后的错误消息或用户交互

    # 元数据
    project_type: str
    framework: Optional[str]
    platform: str  # "windows" or "linux"
    source_log: str
    timestamp: str

    # 统计信息
    retry_count: int  # 重试次数
    diagnostic_count: int  # 诊断命令数量

    # 可能的原因(LLM 分析)
    potential_causes: List[str]  # 可能的根本原因
    requires_manual: bool  # 是否需要人工干预

    def get_failure_content(self) -> str:
        """生成失败案例的完整描述,用于向量化存储"""
        lines = []
        lines.append(f"## Failed Case: {self.initial_command[:100]}")
        lines.append(f"Error: {self.initial_error[:300]}")
        lines.append(f"Summary: {self.error_summary}")
        lines.append("")

        if self.attempted_steps:
            lines.append("### Attempted Solutions (None Worked):")
            for step in self.attempted_steps:
                status = "✓" if step.success else "✗"
                lines.append(f"  {status} {step.command[:80]}")
                if step.reasoning:
                    lines.append(f"     Reason: {step.reasoning[:100]}")

        if self.diagnostic_findings:
            lines.append("")
            lines.append("### Diagnostic Findings:")
            for finding in self.diagnostic_findings:
                lines.append(f"  - {finding}")

        lines.append("")
        lines.append(f"### Outcome: {self.termination_reason}")
        lines.append(f"Message: {self.termination_message[:200]}")

        if self.potential_causes:
            lines.append("")
            lines.append("### Possible Root Causes:")
            for cause in self.potential_causes:
                lines.append(f"  - {cause}")

        if self.requires_manual:
            lines.append("")
            lines.append("⚠️ This issue requires manual intervention")

        return "\n".join(lines)
```

### 2. 扩展 RawExperience

```python
@dataclass
class RawExperience:
    """原始经验数据(扩展)"""

    id: str

    # 二选一:要么是成功案例,要么是失败案例
    chain: Optional[ResolutionChain] = None  # 成功解决的链
    failure: Optional[FailurePattern] = None  # 未解决的失败

    content: str  # 统一的内容表示(用于向量化)

    # 元数据
    project_type: str
    framework: Optional[str]
    source_log: str
    timestamp: str
    processed: bool

    # 新增:经验类型
    experience_type: str  # "resolution" or "failure"

    def is_resolution(self) -> bool:
        return self.chain is not None

    def is_failure(self) -> bool:
        return self.failure is not None
```

## 提取逻辑改进

### 修改 `_extract_single_chain()`

```python
def _extract_single_chain(
    self,
    steps: List[dict],
    start_index: int,
    context: dict,
    source_log: str
) -> Optional[Union[ResolutionChain, FailurePattern]]:
    """从某个失败点提取经验(可能是解决方案或失败模式)"""

    # ... 现有代码 ...

    # 如果找到解决方案,返回 ResolutionChain
    if resolution_index is not None:
        return ResolutionChain(...)

    # === 新增:如果没找到解决方案,检查是否值得记录为失败案例 ===
    if self._is_valuable_failure(chain_steps, steps, start_index):
        return self._create_failure_pattern(
            chain_steps,
            failed_cmd,
            error_msg,
            steps,
            start_index,
            context,
            source_log
        )

    return None
```

### 新增方法:判断失败是否有价值

```python
def _is_valuable_failure(
    self,
    chain_steps: List[ResolutionStep],
    all_steps: List[dict],
    start_index: int
) -> bool:
    """判断失败案例是否值得记录"""

    # 1. 至少尝试过 2 次(包括初始失败)
    if len(chain_steps) < 2:
        return False

    # 2. 有诊断过程或多次重试
    diagnostic_count = sum(1 for s in chain_steps if s.is_diagnostic)
    retry_count = sum(1 for s in chain_steps if not s.is_diagnostic and not s.success)

    if diagnostic_count == 0 and retry_count < 2:
        return False

    # 3. 检查结束原因
    # 查看这个失败链之后的几步,看是否有明确的结束信号
    max_check = min(start_index + len(chain_steps) + 3, len(all_steps))
    for i in range(start_index + len(chain_steps), max_check):
        step = all_steps[i]

        # 如果后面有 ask_user,说明遇到了需要人工介入的问题
        if "ask_user" in step.get("action", ""):
            return True

        # 如果后面有 step_failed,说明明确放弃了
        if "step_failed" in step.get("action", ""):
            return True

    # 4. 检查是否因为达到最大迭代次数
    if len(chain_steps) >= 8:  # 多次尝试但都失败
        return True

    return False
```

### 新增方法:创建失败模式

```python
def _create_failure_pattern(
    self,
    chain_steps: List[ResolutionStep],
    failed_cmd: str,
    error_msg: str,
    all_steps: List[dict],
    start_index: int,
    context: dict,
    source_log: str
) -> FailurePattern:
    """创建失败模式记录"""

    # 提取诊断发现
    diagnostic_findings = []
    for step in chain_steps:
        if step.is_diagnostic and step.stdout:
            # 从诊断命令的输出中提取关键信息
            finding = f"{step.command}: {step.stdout[:200]}"
            diagnostic_findings.append(finding)

    # 确定结束原因
    termination_reason = "unknown"
    termination_message = ""

    # 查看链之后的步骤
    end_index = start_index + len(chain_steps)
    if end_index < len(all_steps):
        next_step = all_steps[end_index]
        action = next_step.get("action", "")

        if "ask_user" in action:
            termination_reason = "ask_user"
            termination_message = next_step.get("question", "")
        elif "step_failed" in action:
            termination_reason = "step_failed"
            termination_message = next_step.get("message", "")

    # 如果还是未知,检查是否达到最大迭代
    if termination_reason == "unknown" and len(chain_steps) >= 8:
        termination_reason = "max_iterations"
        termination_message = "Exceeded maximum retry attempts"

    # 统计
    retry_count = sum(1 for s in chain_steps if not s.is_diagnostic and not s.success)
    diagnostic_count = sum(1 for s in chain_steps if s.is_diagnostic)

    # 生成 ID
    chain_id = hashlib.md5(
        f"{failed_cmd}:{error_msg}:{source_log}:{start_index}".encode()
    ).hexdigest()[:12]

    # 平台检测
    platform = "windows" if "powershell" in context.get("host_info", "").lower() else "linux"

    return FailurePattern(
        id=f"failure_{chain_id}",
        initial_command=failed_cmd,
        initial_error=error_msg[:500],
        error_summary="",  # 待 LLM 提炼
        attempted_steps=[s for s in chain_steps if not s.is_diagnostic],
        diagnostic_findings=diagnostic_findings,
        termination_reason=termination_reason,
        termination_message=termination_message,
        project_type=context.get("project_type", "unknown"),
        framework=context.get("framework"),
        platform=platform,
        source_log=source_log,
        timestamp=datetime.now().isoformat(),
        retry_count=retry_count,
        diagnostic_count=diagnostic_count,
        potential_causes=[],  # 待 LLM 分析
        requires_manual=termination_reason in ["ask_user", "step_failed"]
    )
```

## LLM 提炼失败案例

### 新增提示词:FAILURE_ANALYSIS_PROMPT

```python
FAILURE_ANALYSIS_PROMPT = """# Analyze Failed Deployment Case

You are analyzing a deployment failure that was NOT successfully resolved.
Your goal is to extract useful learnings from this failure for future reference.

## Failed Case Details

**Initial Command**: {initial_command}

**Error Message**:
{initial_error}

**Attempted Solutions** (None worked):
{attempted_steps}

**Diagnostic Findings**:
{diagnostic_findings}

**How It Ended**: {termination_reason}
{termination_message}

**Platform**: {platform}
**Project Type**: {project_type}

## Your Tasks

1. **Summarize the error** (2-3 sentences)
   - What is the core problem?
   - What makes this error difficult to resolve?

2. **Identify potential root causes** (list 2-4)
   - Why might this error occur?
   - What are the most likely underlying issues?

3. **Classify the failure type**:
   - "needs_manual_intervention": Requires user action (service not installed, credentials needed, etc.)
   - "configuration_required": Missing or incorrect configuration
   - "environment_issue": System environment problem (wrong OS, missing dependencies)
   - "insufficient_permissions": Permission/access issues
   - "unknown": Cannot determine from available information

4. **Suggest what to try next** (if encountered again):
   - What diagnostic commands would help?
   - What solutions haven't been tried yet?
   - Should this be escalated to the user immediately?

5. **Extract keywords** for future matching:
   - Error message keywords
   - Related technologies/services
   - Platform-specific terms

## Output Format

Respond with JSON:
```json
{{
  "error_summary": "Brief summary of the core problem",
  "potential_causes": [
    "Cause 1",
    "Cause 2"
  ],
  "failure_type": "needs_manual_intervention",
  "next_steps": [
    "Diagnostic command or action to try",
    "Another suggestion"
  ],
  "requires_immediate_escalation": true/false,
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}
```

Focus on what can be learned from this failure to handle similar cases better in the future.
"""
```

### 提炼器实现

```python
class FailureRefiner:
    """提炼失败案例"""

    def __init__(self, llm_config: dict):
        self.llm_config = llm_config

    def refine_failure(self, failure: FailurePattern) -> FailurePattern:
        """使用 LLM 提炼失败案例"""

        # 格式化尝试步骤
        attempted_steps_text = "\n".join([
            f"  {i+1}. {s.command}\n     Result: {s.stderr[:100] if s.stderr else 'No output'}"
            for i, s in enumerate(failure.attempted_steps)
        ])

        # 格式化诊断发现
        diagnostic_text = "\n".join([
            f"  - {finding}"
            for finding in failure.diagnostic_findings
        ]) if failure.diagnostic_findings else "  (None)"

        # 构建提示
        prompt = FAILURE_ANALYSIS_PROMPT.format(
            initial_command=failure.initial_command,
            initial_error=failure.initial_error,
            attempted_steps=attempted_steps_text,
            diagnostic_findings=diagnostic_text,
            termination_reason=failure.termination_reason,
            termination_message=failure.termination_message,
            platform=failure.platform,
            project_type=failure.project_type
        )

        # 调用 LLM
        response = self._call_llm(prompt)

        # 解析响应
        try:
            analysis = json.loads(response)

            # 更新失败模式
            failure.error_summary = analysis.get("error_summary", "")
            failure.potential_causes = analysis.get("potential_causes", [])
            failure.requires_manual = analysis.get("requires_immediate_escalation", False)

            # 可以添加更多字段存储 next_steps 和 keywords

        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM response for failure {failure.id}")

        return failure

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM(复用现有的 LLM 客户端)"""
        # 实现细节...
        pass
```

## 检索和使用失败案例

### 1. 检索时区分成功和失败案例

```python
class ExperienceRetriever:

    def get_formatted_experiences(
        self,
        project_type: str = None,
        framework: str = None,
        query: str = None,
        max_results: int = 5,
        include_failures: bool = True  # 新增:是否包含失败案例
    ) -> str:
        """获取格式化的经验"""

        # ... 现有检索逻辑 ...

        # 分别获取成功案例和失败案例
        resolutions = [exp for exp in results if exp.is_resolution()]
        failures = [exp for exp in results if exp.is_failure() and include_failures]

        # 格式化输出
        lines = []

        if resolutions:
            lines.append("## Past Successful Resolutions:")
            for exp in resolutions[:max_results]:
                lines.append(exp.content)
                lines.append("---")

        if failures:
            lines.append("\n## Known Failure Patterns (No Solution Found):")
            lines.append("These cases required manual intervention or remain unresolved:")
            for exp in failures[:2]:  # 最多显示 2 个失败案例
                lines.append(exp.content)
                lines.append("---")

        return "\n".join(lines)
```

### 2. 提示词中的使用指导

在 `agent.py` 的提示中:

```python
# 如果检索到失败案例,添加特别说明
if has_failure_patterns:
    prompt_parts.append("""
## ⚠️ Known Difficult Cases

The following similar issues have been encountered before but NOT successfully resolved.
They typically require manual intervention:

{failure_patterns}

If you encounter these patterns:
1. Try the diagnostic steps suggested
2. If diagnostics confirm the issue, escalate to user immediately
3. Don't waste iterations on methods that have already failed
""")
```

## 价值体现

### 1. 避免无效重试

**场景**: Docker Desktop 服务未安装

```
检索到失败案例:
  Error: "docker: command not found"
  Attempted: sudo apt install docker.io (failed - package not in repo)
  Attempted: sudo systemctl start docker (failed - service doesn't exist)
  Requires: Manual Docker Desktop installation on Windows

LLM 看到后:
  → 不再尝试 apt install 或 systemctl
  → 直接 ask_user 让用户安装 Docker Desktop
```

### 2. 快速识别人工需求

**场景**: 需要云服务凭证

```
检索到失败案例:
  Error: "authentication failed: invalid credentials"
  Attempted: Check .env file, regenerate token
  Requires: User needs to provide valid API key manually

LLM 看到后:
  → 第一次遇到认证错误就 ask_user
  → 而不是多次尝试不同的配置
```

### 3. 学习平台特定限制

**场景**: Windows 上的某些操作不可行

```
检索到失败案例:
  Error: "operation not permitted on Windows"
  Platform: Windows
  Requires: Use alternative approach (PowerShell instead of bash)

LLM 看到后:
  → 在 Windows 上避免使用 Linux 特定命令
  → 直接使用 Windows 替代方案
```

## 实施步骤

### 阶段 1: 数据模型(1 天)
1. 创建 `FailurePattern` 数据类
2. 扩展 `RawExperience` 支持失败案例
3. 更新数据库/存储结构

### 阶段 2: 提取逻辑(1-2 天)
4. 修改 `_extract_single_chain()` 支持返回失败模式
5. 实现 `_is_valuable_failure()` 判断逻辑
6. 实现 `_create_failure_pattern()` 创建逻辑
7. 测试提取逻辑

### 阶段 3: LLM 提炼(1 天)
8. 编写 `FAILURE_ANALYSIS_PROMPT`
9. 实现 `FailureRefiner` 类
10. 集成到经验处理流程

### 阶段 4: 检索和使用(1 天)
11. 更新检索逻辑区分成功/失败案例
12. 更新提示词引导 LLM 使用失败案例
13. 添加失败案例展示逻辑

### 阶段 5: 测试(1 天)
14. 用历史失败日志测试提取
15. 验证 LLM 提炼质量
16. 检查检索准确性

## 关键设计考虑

### 1. 存储效率
- 失败案例可能比成功案例更多
- 只保留"有价值"的失败(多次尝试、有诊断、需人工)
- 定期清理低质量失败案例

### 2. 检索平衡
- 优先展示成功案例
- 失败案例作为补充警示
- 避免"负面学习"过度影响决策

### 3. 更新机制
- 如果失败案例后来被解决,转换为成功案例
- 合并相似的失败模式
- 标记过时的失败案例(环境已改变)

## 总结

通过**双轨学习机制**:
- ✅ 成功案例:学习"如何解决"
- ✅ 失败案例:学习"何时放弃""何时求助"

**核心价值**:
1. 减少无效重试,节省时间
2. 快速识别需要人工介入的情况
3. 积累"已知难题"知识库
4. 提高系统智能度和用户体验

失败也是宝贵的经验! 🎯
