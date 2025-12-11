# 自由输入功能指南

## 概述

Auto-Deployer 的人机协作系统现在全面支持**自由输入**功能。在大多数选择场景中，除了预设选项外，用户还可以输入自定义的命令、配置值或指令。

## 功能特性

### 1. 三种输入方式

当系统询问选择时，用户有三种方式提供输入：

#### 方式 1: 选择预设选项
```
请选择 [1]:
输入: 1
```
直接输入选项编号 (1, 2, 3...) 选择预设选项。

#### 方式 2: 进入自定义输入模式
```
请选择:
输入: 0
💬 请输入自定义值 (例如命令、配置值等): npm install --force
```
输入 `0` 会进入自定义输入模式，可以输入任何文本。

#### 方式 3: 直接输入文本
```
请选择:
输入: 使用备用方案部署
✅ 已接收自定义输入: 使用备用方案部署
```
直接输入任意文本，系统会自动识别为自定义输入。

### 2. 应用场景

自由输入功能已启用于以下场景：

#### 场景 A: 部署计划确认
```
🤔 Agent 需要您的输入:
   是否继续执行此部署计划?

   ℹ️  Strategy: Docker容器化部署
Steps: 5个
Estimated: 10分钟

   选项:
   [1] Yes, proceed with this plan (默认)
   [2] No, cancel deployment
   [0] 自定义输入 (您可以输入自己的指令或值)
   💡 提示: 您也可以直接输入文本作为自定义值

   请选择 [1]:
```

**自定义输入示例:**
- `先让我检查一下配置文件`
- `暂停，我需要备份数据库`
- `修改第3步的端口配置为8080`

#### 场景 B: 错误恢复
```
🔧 Agent 需要您的输入:
   步骤 '安装依赖' 失败: npm install 返回错误码 1
   您想怎么做?

   选项:
   [1] Retry this step
   [2] Skip and continue
   [3] Abort deployment
   [0] 自定义输入 (您可以输入自己的指令或值)
   💡 提示: 您也可以直接输入文本作为自定义值

   请选择:
```

**自定义输入示例:**
- `npm install --force` (使用强制安装)
- `rm -rf node_modules && npm install` (清理后重装)
- `切换到国内镜像源再重试`
- `跳过此包，手动安装`

#### 场景 C: 配置决策
```
🤔 Agent 需要您的输入:
   检测到端口 3000 已被占用，请选择新端口:

   ℹ️  当前应用: React开发服务器

   选项:
   [1] 3001 (默认)
   [2] 5173
   [3] 8080
   [0] 自定义输入 (您可以输入自己的指令或值)
   💡 提示: 您也可以直接输入文本作为自定义值

   请选择 [1]:
```

**自定义输入示例:**
- `4000` (使用其他端口号)
- `随机选择一个可用端口`
- `使用环境变量 $PORT`

## 技术细节

### InteractionRequest 参数

```python
request = InteractionRequest(
    question="您的问题",
    input_type=InputType.CHOICE,
    options=["选项1", "选项2", "选项3"],
    category=QuestionCategory.DECISION,
    allow_custom=True,  # 启用自由输入
)
```

### InteractionResponse 字段

```python
response = handler.ask(request)

# 检查是否为自定义输入
if response.is_custom:
    print(f"用户自定义输入: {response.value}")
else:
    print(f"用户选择了选项 {response.selected_option}: {response.value}")
```

### allow_custom 参数说明

| 场景 | allow_custom | 说明 |
|------|--------------|------|
| 部署计划确认 | `True` | 允许用户提供自定义反馈或指令 |
| 错误恢复选择 | `True` | 允许用户提供自定义修复命令 |
| 配置决策 | `True` | 允许用户提供自定义配置值 |
| 危险操作确认 | 视情况而定 | 某些情况下可能需要限制为预设选项 |

## 用户体验改进

### 1. 清晰的提示信息
- 明确告知用户可以输入 `0` 进入自定义模式
- 提示用户可以直接输入文本
- 自定义输入时提供示例说明

### 2. 输入验证
- 自定义输入不能为空
- 无效的选项编号会给出清晰的错误提示
- 支持默认值，直接回车使用默认值

### 3. 反馈确认
```
✅ 已接收自定义输入: npm install --force
```
当用户直接输入文本时，系统会明确确认已接收到自定义输入。

## 示例代码

运行示例测试脚本:

```bash
python examples/test_custom_input.py
```

该脚本演示了各种自由输入场景的使用方法。

## 实现文件

相关代码文件：

- [src/auto_deployer/interaction/handler.py](../src/auto_deployer/interaction/handler.py) - 核心交互处理逻辑
- [src/auto_deployer/workflow.py](../src/auto_deployer/workflow.py) - 工作流中的计划确认
- [src/auto_deployer/orchestrator/orchestrator.py](../src/auto_deployer/orchestrator/orchestrator.py) - 编排器中的错误恢复
- [src/auto_deployer/llm/agent.py](../src/auto_deployer/llm/agent.py) - Legacy Agent 的计划确认

## 最佳实践

### 何时使用自由输入

✅ **建议启用:**
- 用户可能需要提供特殊指令或参数
- 预设选项无法覆盖所有情况
- 需要灵活的错误恢复策略
- 配置值可能有无限种可能

❌ **建议禁用:**
- 仅需二元决策 (是/否)
- 必须从固定选项中选择
- 涉及安全敏感操作

### 设计良好的选项列表

```python
# 好的设计: 提供常见选项 + 自由输入
options = [
    "使用默认配置 (推荐)",
    "使用生产环境配置",
    "使用测试环境配置"
]
allow_custom = True  # 用户可以输入自定义配置路径

# 不好的设计: 选项太少，强制自由输入
options = ["是", "否"]
allow_custom = True  # 这种情况应该用 InputType.CONFIRM
```

## 未来增强

计划中的功能改进：

- [ ] 自定义输入的历史记录和自动补全
- [ ] 基于上下文的输入建议
- [ ] 自定义输入的安全性检查 (防止注入攻击)
- [ ] 富文本编辑器支持 (多行输入)
- [ ] 自定义输入模板系统

## 常见问题

### Q1: 如何禁用某个场景的自由输入？

设置 `allow_custom=False`:

```python
request = InteractionRequest(
    question="确认删除所有数据?",
    options=["确认删除", "取消"],
    allow_custom=False,  # 强制只能选择预设选项
)
```

### Q2: 如何处理用户的自定义输入？

检查 `response.is_custom` 字段:

```python
response = handler.ask(request)
if response.is_custom:
    # 用户提供了自定义输入
    custom_command = response.value
    # 执行自定义命令或逻辑
else:
    # 用户选择了预设选项
    selected_option = response.selected_option
```

### Q3: 自定义输入会传递给 LLM 吗？

是的。用户的自定义输入会包含在 LLM 的上下文中，LLM 会根据用户的指令调整行为。例如，如果用户输入 "使用备用端口 4000"，LLM 会理解并在后续步骤中使用该端口。

## 参考资料

- [交互系统模块文档](./modules/interaction.md)
- [测试用例](../tests/test_interaction.py)
- [示例脚本](../examples/test_custom_input.py)
