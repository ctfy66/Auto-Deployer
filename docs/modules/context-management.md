# 增强型上下文管理系统

> 模块路径: `src/auto_deployer/orchestrator/`  
> 版本: 1.0  
> 更新日期: 2025-12-13

## 概述

增强型上下文管理系统解决了多步骤部署过程中的上下文传递问题。传统方案要么传递完整对话历史（Token 爆炸），要么只传递简单的 key-value（信息丢失）。本系统采用 **结构化产出 + 滚动摘要** 的混合方案，在保持 Token 效率的同时确保跨步骤信息一致性。

## 设计目标

| 目标         | 实现方式                   |
| ------------ | -------------------------- |
| Token 效率   | 摘要自动截断，控制大小     |
| 跨步骤一致性 | 结构化产出 + 全局摘要注入  |
| 产出质量保证 | 强制验证，summary 字段必填 |
| 向后兼容     | 保留原有 outputs Dict 字段 |

## 核心组件

### 1. StepOutputs - 结构化步骤产出

每个步骤完成时必须提供的结构化产出，用于传递关键信息给后续步骤。

```python
@dataclass
class StepOutputs:
    summary: str                                    # 必填：一句话总结
    environment_changes: Dict[str, Any]             # 环境变更
    new_configurations: Dict[str, str]              # 新增配置值
    artifacts: List[str]                            # 创建的关键文件
    services_started: List[Dict[str, Any]]          # 启动的服务
    custom_data: Dict[str, Any]                     # 自定义数据
    issues_resolved: List[Dict[str, str]]           # 解决的问题
```

**使用示例**：

```python
outputs = StepOutputs(
    summary="Installed Node.js 18.17.0 via nvm",
    environment_changes={"node_version": "18.17.0", "npm_version": "9.6.7"},
    new_configurations={"NODE_ENV": "production"},
    artifacts=["/home/user/.nvm/versions/node/v18.17.0"],
    issues_resolved=[{"issue": "Node.js not found", "resolution": "Installed via nvm"}]
)
```

### 2. ExecutionSummary - 全局执行摘要

在整个部署过程中维护的滚动摘要，为后续步骤提供全局上下文。

```python
@dataclass
class ExecutionSummary:
    project_name: str                               # 项目名
    deploy_dir: str                                 # 部署目录
    strategy: str                                   # 部署策略
    environment: Dict[str, Any]                     # 当前环境状态
    completed_actions: List[str]                    # 已完成操作列表
    configurations: Dict[str, str]                  # 已确定的配置值
    resolved_issues: List[Dict[str, str]]           # 已解决的问题
    last_updated: str                               # 最后更新时间
```

**生成 LLM 可读上下文**：

```python
context = summary.to_prompt_context()
# 输出:
# # Current Deployment State
# - Project: my-app
# - Deploy Directory: /home/user/my-app
# - Strategy: traditional
#
# ## Environment
# - node_version: 18.17.0
# ...
```

### 3. SummaryManager - 摘要管理器

负责摘要的更新和大小控制，防止 Token 爆炸。

```python
class SummaryManager:
    MAX_COMPLETED_ACTIONS = 15      # 最多保留 15 条操作记录
    MAX_RESOLVED_ISSUES = 5         # 最多保留 5 条问题记录

    def merge_step_outputs(self, step_name, step_category, outputs: StepOutputs) -> None:
        """合并步骤产出到全局摘要"""

    def get_summary(self) -> ExecutionSummary:
        """获取当前摘要"""

    def get_prompt_context(self) -> str:
        """获取用于 LLM prompt 的摘要文本"""
```

## 数据流

```
                    ┌─────────────────────────────────────┐
                    │       DeploymentOrchestrator        │
                    │  ┌─────────────────────────────┐    │
                    │  │     SummaryManager          │    │
                    │  │  ┌───────────────────────┐  │    │
                    │  │  │  ExecutionSummary     │  │    │
                    │  │  └───────────────────────┘  │    │
                    │  └─────────────────────────────┘    │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
   ┌─────────┐              ┌─────────┐              ┌─────────┐
   │ Step 1  │              │ Step 2  │              │ Step 3  │
   │         │              │         │              │         │
   │ 输入:   │              │ 输入:   │              │ 输入:   │
   │ - 初始  │              │ - 摘要  │              │ - 摘要  │
   │   摘要  │              │ - Step1 │              │ - Step2 │
   │         │              │   产出  │              │   产出  │
   │ 输出:   │              │         │              │         │
   │ - Step  │──合并──────▶│ 输出:   │──合并──────▶│ 输出:   │
   │   Outputs│              │ - Step  │              │ - Step  │
   └─────────┘              │   Outputs│              │   Outputs│
                            └─────────┘              └─────────┘
```

## 与现有系统的集成

### StepContext 增强

```python
@dataclass
class StepContext:
    # ... 原有字段 ...

    # 新增字段
    structured_outputs: Optional[StepOutputs] = None      # 结构化产出
    execution_summary: Optional[ExecutionSummary] = None  # 全局摘要引用
    predecessor_outputs: Dict[int, StepOutputs] = field(default_factory=dict)  # 前置步骤产出
```

### StepResult 增强

```python
@dataclass
class StepResult:
    # ... 原有字段 ...

    # 新增字段
    structured_outputs: Optional[StepOutputs] = None

    @classmethod
    def succeeded(cls, outputs=None, structured_outputs=None) -> "StepResult":
        ...
```

### Orchestrator 集成

```python
class DeploymentOrchestrator:
    def run(self, plan, deploy_ctx):
        # 初始化摘要管理器
        self.summary_manager = SummaryManager(
            project_name=project_name,
            deploy_dir=deploy_ctx.deploy_dir,
            strategy=plan.strategy,
        )

        for step in plan.steps:
            # 创建上下文时注入摘要
            step_ctx = self._create_step_context(step, completed_outputs)

            result = self.step_executor.execute(step_ctx, deploy_ctx)

            # 合并产出到摘要
            if result.structured_outputs:
                self.summary_manager.merge_step_outputs(
                    step_name=step.name,
                    step_category=step.category,
                    outputs=result.structured_outputs,
                )
```

## LLM Prompt 模板

步骤执行时，LLM 会收到包含全局摘要的系统提示：

```
You are a deployment agent executing a specific deployment step.

# Current Deployment State
- Project: my-app
- Deploy Directory: /home/user/my-app
- Strategy: traditional

## Environment
- node_version: 18.17.0
- pm2_installed: True

## Completed Actions
- [PREREQUISITE] Install Node.js: Installed Node.js 18.17.0

---

# Current Step
- **Step 2**: Build Application
- **Goal**: Run npm build to create production bundle
- **Success Criteria**: dist/ folder exists with index.js

---

When step is COMPLETE, you MUST provide:
{
  "action": "step_done",
  "outputs": {
    "summary": "REQUIRED: One sentence describing what was accomplished",
    ...
  }
}
```

## 产出验证

`StepExecutor._validate_outputs()` 确保 LLM 返回有效的结构化产出：

```python
def _validate_outputs(self, outputs_dict: Optional[dict]) -> Optional[StepOutputs]:
    if not outputs_dict:
        return None

    summary = outputs_dict.get("summary")
    if not summary or not isinstance(summary, str):
        # 尝试从其他字段生成摘要
        summary = outputs_dict.get("message", "Step completed")

    return StepOutputs(
        summary=summary,
        environment_changes=outputs_dict.get("environment_changes", {}),
        # ...
    )
```

## 配置参数

`SummaryManager` 的截断参数可通过类常量调整：

| 参数                     | 默认值 | 说明                     |
| ------------------------ | ------ | ------------------------ |
| `MAX_COMPLETED_ACTIONS`  | 15     | 最多保留多少条已完成操作 |
| `MAX_RESOLVED_ISSUES`    | 5      | 最多保留多少条已解决问题 |
| `MAX_ENVIRONMENT_KEYS`   | 30     | 环境变量数量警告阈值     |
| `MAX_CONFIGURATION_KEYS` | 20     | 配置值数量警告阈值       |

## 日志记录

部署日志会包含结构化产出和执行摘要：

```json
{
  "version": "2.0",
  "steps": [
    {
      "step_id": 1,
      "step_name": "Install Node.js",
      "outputs": {...},
      "structured_outputs": {
        "summary": "Installed Node.js 18.17.0 via nvm",
        "environment_changes": {"node_version": "18.17.0"},
        ...
      }
    }
  ],
  "execution_summary": {
    "project_name": "my-app",
    "environment": {...},
    "completed_actions": [...]
  }
}
```

## 与其他方案的对比

| 特性         | 完整历史传递 | 简单 Dict | 本方案              |
| ------------ | ------------ | --------- | ------------------- |
| Token 效率   | ❌ 差        | ✅ 好     | ✅ 好               |
| 信息完整性   | ✅ 高        | ❌ 低     | ✅ 高               |
| 跨步骤一致性 | ✅ 高        | ⚠️ 中     | ✅ 高               |
| 大小可控     | ❌ 不可控    | ✅ 可控   | ✅ 可控（自动截断） |
| 结构化程度   | ❌ 低        | ⚠️ 中     | ✅ 高               |

## 文件清单

```
src/auto_deployer/orchestrator/
├── __init__.py           # 模块导出
├── models.py             # ExecutionSummary, StepOutputs, StepContext, StepResult
├── summary_manager.py    # SummaryManager 类
├── prompts.py            # LLM prompt 模板
├── step_executor.py      # 步骤执行器（含产出验证）
└── orchestrator.py       # 编排器（集成摘要管理）

tests/
└── test_context_management.py   # 单元测试（20 个测试用例）
```

## 未来扩展

1. **动态计划调整**：根据步骤产出自动调整后续步骤
2. **向量化摘要**：将摘要存入向量数据库，支持语义检索
3. **摘要压缩**：使用 LLM 对过长摘要进行智能压缩
4. **中断恢复**：基于摘要实现部署中断后的恢复
