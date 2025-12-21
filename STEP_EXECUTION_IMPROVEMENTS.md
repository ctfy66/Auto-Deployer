# 步骤执行改进说明

## 改进日期

2025-12-21

## 改进目标

解决执行步骤 agent 无法获取规划阶段建议命令的问题，并简化步骤输出结构以减少 token 消耗。

## 问题背景

在之前的实现中发现：

1. **规划与执行脱节**：规划阶段生成的 `estimated_commands`（如端口 4090）没有传递给执行步骤
2. **agent 盲目猜测**：执行步骤的 agent 只能根据目标描述自行推断，导致错误（如猜测 8000 端口而不是 4090）
3. **输出过于复杂**：StepOutputs 包含 7 个字段，大部分情况下用不到，增加 token 消耗

## 实施的改进

### 1. 添加 `estimated_commands` 到执行上下文

**修改文件**：

- `src/auto_deployer/orchestrator/models.py` - StepContext 数据类
- `src/auto_deployer/orchestrator/orchestrator.py` - 传递 estimated_commands

**效果**：

```python
# 之前：执行步骤看不到规划建议
StepContext(goal="验证应用可访问性", ...)

# 现在：执行步骤能看到建议的命令
StepContext(
    goal="验证应用可访问性",
    estimated_commands=[
        "Start-Process 'http://localhost:4090'",
        "Invoke-WebRequest -Uri http://localhost:4090"
    ]
)
```

### 2. 在提示词中显示建议命令

**修改文件**：

- `src/auto_deployer/orchestrator/prompts.py` - 系统提示模板
- `src/auto_deployer/prompts/execution_step.py` - 执行步骤提示
- `src/auto_deployer/orchestrator/step_executor.py` - 传递参数

**效果**：
提示词新增"Suggested Commands (from Planning Phase)"部分：

```
## Suggested Commands (from Planning Phase)
The planner suggested these commands for reference:
1. `Start-Process 'http://localhost:4090'`
2. `Invoke-WebRequest -Uri http://localhost:4090 -UseBasicParsing`

Note: These are suggestions. Adapt them based on actual environment conditions.
```

### 3. 简化步骤输出结构

**修改文件**：

- `src/auto_deployer/orchestrator/models.py` - StepOutputs 数据类
- `src/auto_deployer/orchestrator/step_executor.py` - 输出验证
- `src/auto_deployer/orchestrator/summary_manager.py` - 摘要管理
- `src/auto_deployer/orchestrator/prompts.py` - 输出 schema

**之前的复杂结构**：

```python
StepOutputs(
    summary="...",
    environment_changes={},      # 7个字段
    new_configurations={},       # 大部分情况下空着
    artifacts=[],
    services_started=[],
    custom_data={},
    issues_resolved=[]
)
```

**现在的精简结构**：

```python
StepOutputs(
    summary="Started Node.js service on port 4090",
    key_info={"port": 4090, "service": "nodejs"}  # 只记录关键信息
)
```

### 4. 更新输出格式说明

**修改的输出示例**：

```json
{
  "action": "step_done",
  "outputs": {
    "summary": "One sentence describing what was accomplished",
    "key_info": {
      "port": 4090, // 如果启动了服务
      "service": "nodejs", // 服务名称
      "config_file": ".env" // 关键配置文件
    }
  }
}
```

## 预期效果

### 1. 解决端口错误问题

- **之前**：第 6 步 agent 猜测 8000 端口（错误）
- **现在**：agent 看到规划建议的 4090 端口（正确）

### 2. 减少 token 消耗

- 输出结构从 7 个字段减少到 2 个字段
- 只传递必要的关键信息
- 减少约 30-40%的输出相关 token

### 3. 提高信息传递准确性

- 前置步骤的关键信息（如端口号）能正确传递给后续步骤
- 避免信息丢失导致的错误猜测

## 向后兼容性

- 保留了旧的输出字段支持（通过默认值）
- 日志结构保持兼容
- 不影响已有的部署流程

## 测试验证

运行 `python verify_improvements.py` 可验证所有改进已正确实施。

所有 9 项检查均通过：

- ✓ estimated_commands 添加到 StepContext
- ✓ StepOutputs 简化为 summary + key_info
- ✓ Orchestrator 传递 estimated_commands
- ✓ 提示词显示建议命令
- ✓ 输出格式在所有提示中简化
- ✓ 验证和摘要管理器已更新

## 下一步建议

1. 实际部署测试，验证 agent 是否正确使用建议命令
2. 监控 token 使用量，确认减少效果
3. 根据实际使用情况调整 key_info 的标准化格式
