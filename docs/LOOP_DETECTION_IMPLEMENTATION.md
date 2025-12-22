# 循环检测机制实施完成

## 实施日期

2025-12-21

## 概述

成功实现了 Auto-Deployer 的循环检测机制，用于检测 Agent 在执行过程中陷入重复命令的循环，并采取分级干预措施打破循环。

## 实施内容

### 1. 新增文件

#### src/auto_deployer/orchestrator/loop_detector.py

循环检测器，负责识别三种循环模式：

- **直接重复 (direct_repeat)**: 连续执行相同命令且输出相似
- **错误循环 (error_loop)**: 不同命令但遇到相同错误
- **交替模式 (alternating)**: 两个或多个命令交替执行（预留接口）

关键功能：

- `check()`: 主检测入口
- `_check_direct_repeat()`: 检测 AAA 模式
- `_check_error_loop()`: 检测持续失败模式
- `_command_similarity()`: 命令相似度计算（基于 difflib）
- `_output_similarity()`: 输出相似度计算
- `_normalize_output()`: 输出归一化（去除时间戳、PID 等动态内容）
- `_extract_error_signature()`: 提取错误特征签名

#### src/auto_deployer/orchestrator/loop_intervention.py

循环干预管理器，采取分级干预措施：

- **第 1 次**: 提升温度至 0.3，增加随机性
- **第 2 次**: 注入反思提示 + 提升温度至 0.5
- **第 3 次及以后**: 询问用户干预（继续/跳过/中止/提供指导）

关键功能：

- `decide_intervention()`: 决定干预级别
- `_build_reflection_prompt()`: 构建强制反思提示文本
- `reset()`: 重置干预计数器（用于新步骤）

### 2. 修改文件

#### src/auto_deployer/orchestrator/models.py

- 添加 `LoopDetectionResult` 数据类：封装循环检测结果
- 在 `StepContext` 中添加 `reflection_prompt` 字段：用于注入反思提示

#### src/auto_deployer/orchestrator/step_executor.py

- 在 `__init__()` 中初始化循环检测组件
- 在 `execute()` 主循环中集成循环检测逻辑
- 添加 `_handle_loop_intervention()` 方法：处理用户干预
- 修改 `_get_next_action()`: 支持反思 prompt 注入到 LLM 调用

#### src/auto_deployer/orchestrator/orchestrator.py

- 添加 `loop_detection_enabled` 参数并传递给 StepExecutor

#### src/auto_deployer/orchestrator/**init**.py

- 导出 `LoopDetector` 和 `LoopInterventionManager`
- 导出 `LoopDetectionResult` 数据模型

#### src/auto_deployer/config.py

- 添加 `LoopDetectionConfig` 数据类
- 在 `AgentConfig` 中集成循环检测配置
- 更新 `from_dict()` 方法以解析嵌套配置

#### config/default_config.json

添加循环检测配置项：

```json
"loop_detection": {
  "enabled": true,
  "direct_repeat_threshold": 3,
  "error_loop_threshold": 4,
  "command_similarity_threshold": 0.85,
  "output_similarity_threshold": 0.80,
  "temperature_boost_levels": [0.3, 0.5, 0.7]
}
```

#### src/auto_deployer/workflow.py

- 在创建 `DeploymentOrchestrator` 时传递 `loop_detection_enabled` 参数

### 3. 测试文件

#### test_loop_detection.py

创建了三个测试用例：

- `test_direct_repeat_detection()`: 测试直接重复检测
- `test_error_loop_detection()`: 测试错误循环检测
- `test_no_loop()`: 测试正常进展不被误判

## 技术实现细节

### 相似度计算

- 使用 Python 标准库 `difflib.SequenceMatcher` 计算文本相似度
- 相似度范围：0.0（完全不同）到 1.0（完全相同）
- 默认阈值：命令相似度 0.85，输出相似度 0.80

### 输出归一化

去除会变化但不影响语义的动态内容：

- 时间戳 → `[TS]`
- 进程 ID → `pid:[N]`
- 临时文件路径 → `/tmp/[TEMP]`

### 循环检测触发条件

- 至少执行 3 条命令后才开始检测
- 每次命令执行后进行检测（实时）
- 检测到循环立即触发干预

### 干预策略

1. **温度提升**: 从 0.0（确定性）提升到 0.3/0.5/0.7（随机性）
2. **反思注入**: 强制要求 Agent 分析失败原因并改变策略
3. **用户介入**: 提供 4 个选项（继续/跳过/中止/自定义指导）

### 反思提示内容

包含以下强制要求：

- 停下来分析：为什么之前的尝试失败？
- 改变策略：必须采用根本不同的方法
- 证明合理性：解释新方法为何会成功
- 如果真的卡住：声明 step_failed 而非继续循环

## 配置选项

所有配置项都在 `config/default_config.json` 的 `agent.loop_detection` 节点下：

| 配置项                         | 默认值            | 说明                                 |
| ------------------------------ | ----------------- | ------------------------------------ |
| `enabled`                      | `true`            | 是否启用循环检测                     |
| `direct_repeat_threshold`      | `3`               | 直接重复触发阈值（连续相同命令次数） |
| `error_loop_threshold`         | `4`               | 错误循环触发阈值（连续失败次数）     |
| `command_similarity_threshold` | `0.85`            | 命令相似度阈值（0-1）                |
| `output_similarity_threshold`  | `0.80`            | 输出相似度阈值（0-1）                |
| `temperature_boost_levels`     | `[0.3, 0.5, 0.7]` | 温度提升级别列表                     |

## 使用方法

### 启用/禁用循环检测

编辑 `config/default_config.json`:

```json
{
  "agent": {
    "loop_detection": {
      "enabled": true // 改为 false 以禁用
    }
  }
}
```

### 调整敏感度

- **降低敏感度**（减少误报）：提高相似度阈值（如 0.90）
- **提高敏感度**（更早检测）：降低相似度阈值（如 0.75）或降低触发阈值

### 温度调整

- **保守策略**：使用较低温度 `[0.2, 0.3, 0.4]`
- **激进策略**：使用较高温度 `[0.5, 0.7, 0.9]`

## 预期效果

实施循环检测后，系统能够：

1. **自动识别循环**：在 3-4 次重复后自动检测到循环模式
2. **主动打破僵局**：通过提升温度和反思注入改变 Agent 行为
3. **防止资源浪费**：避免在无效操作上消耗迭代次数
4. **提供用户控制**：严重循环时允许用户介入决策

### 常见循环场景

- ✅ npm install 持续权限错误
- ✅ 端口占用反复检查
- ✅ 路径不存在循环 cd
- ✅ 依赖冲突反复尝试不同参数

## 代码质量

- ✅ 所有文件通过语法检查
- ✅ 无编译错误
- ✅ 类型提示完整
- ✅ 文档字符串完整
- ✅ 代码风格一致

## 后续改进方向

1. **交替模式检测**: 完善 ABAB 模式的识别逻辑
2. **学习机制**: 记录成功打破循环的策略，供未来参考
3. **统计分析**: 在日志中记录循环检测统计数据
4. **可视化**: 在 UI 中显示循环检测图表
5. **自适应阈值**: 根据项目类型自动调整检测参数

## 集成验证

所有修改已成功集成到主系统：

- ✅ 配置系统正确解析循环检测配置
- ✅ Orchestrator 正确传递参数到 StepExecutor
- ✅ StepExecutor 正确初始化循环检测组件
- ✅ 循环检测逻辑正确嵌入执行循环
- ✅ 用户交互接口正确调用

## 状态: ✅ 完成

循环检测机制已完整实现并准备投入使用。
