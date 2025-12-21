# 用户交互可选功能使用指南

## 功能概述

Auto-Deployer 现在支持将用户交互机制设置为可选，并支持多种交互模式：

1. **CLI 模式** (默认): 通过命令行与用户交互
2. **Auto 模式**: 自动模式，遇到交互请求时自动处理
   - **retry 子模式**: 返回 "retry" 触发重新规划
   - **defaults 子模式**: 自动使用默认值

## 配置方式

### 1. 通过配置文件 (`config/default_config.json`)

```json
{
  "interaction": {
    "enabled": true,
    "mode": "cli",
    "auto_retry_on_interaction": true,
    "_comment": "mode options: 'cli' (interactive), 'auto' (auto-retry on interaction), 'callback' (GUI/Web integration)"
  }
}
```

**配置项说明**:

- `enabled`: 是否启用用户交互 (true/false)
- `mode`: 交互模式
  - `"cli"`: 命令行交互（默认）
  - `"auto"`: 自动模式
  - `"callback"`: 回调模式（用于 GUI/Web 集成）
- `auto_retry_on_interaction`: 在 auto 模式下遇到交互时是否自动返回 retry

### 2. 通过命令行参数

```bash
# 使用非交互模式（自动 retry）
auto-deployer deploy --repo <git-url> --local --non-interactive

# 指定 auto 模式行为
auto-deployer deploy --repo <git-url> --local --auto-mode retry    # 触发重新规划
auto-deployer deploy --repo <git-url> --local --auto-mode defaults # 使用默认值
```

## 使用场景

### 场景 1: 完全自动化部署（推荐用于 CI/CD）

**配置文件方式**:

```json
{
  "interaction": {
    "enabled": true,
    "mode": "auto",
    "auto_retry_on_interaction": true
  }
}
```

**命令行方式**:

```bash
auto-deployer deploy --repo https://github.com/user/repo.git --local --non-interactive
```

**行为**:

- 遇到需要用户输入时，自动返回 "retry"
- Agent 会重新思考并尝试其他方案
- 适合无人值守的自动化部署

### 场景 2: 使用默认值的自动部署

**配置文件方式**:

```json
{
  "interaction": {
    "enabled": true,
    "mode": "auto",
    "auto_retry_on_interaction": false
  }
}
```

**命令行方式**:

```bash
auto-deployer deploy --repo https://github.com/user/repo.git --local --auto-mode defaults
```

**行为**:

- 遇到交互请求时自动使用默认值
- 如果没有默认值，选择第一个选项
- 适合有合理默认配置的项目

### 场景 3: 交互式部署（默认）

**配置文件方式**:

```json
{
  "interaction": {
    "enabled": true,
    "mode": "cli"
  }
}
```

**命令行方式**:

```bash
auto-deployer deploy --repo https://github.com/user/repo.git --local
```

**行为**:

- 保持原有交互行为
- Agent 需要输入时会提示用户
- 适合需要人工决策的部署

## 技术实现

### 新增类

#### `InteractionConfig` (config.py)

```python
@dataclass
class InteractionConfig:
    """Configuration for user interaction."""
    enabled: bool = True
    mode: str = "cli"  # "cli" | "auto" | "callback"
    auto_retry_on_interaction: bool = True
```

#### `AutoRetryHandler` (interaction/handler.py)

```python
class AutoRetryHandler(UserInteractionHandler):
    """
    Auto-retry handler for non-interactive mode.
    When asked for input, returns a 'retry' signal to trigger replanning.
    """
```

### 工作流程

1. **配置加载**: 从 `config/default_config.json` 或环境变量加载配置
2. **命令行覆盖**: `--non-interactive` 和 `--auto-mode` 参数可覆盖配置文件
3. **Handler 选择**: `DeploymentWorkflow` 根据配置自动选择合适的 handler
4. **交互处理**:
   - CLI 模式: 提示用户输入
   - Auto+retry 模式: 返回 "retry"，触发 Agent 重新规划
   - Auto+defaults 模式: 使用默认值继续

## 示例输出

### 非交互模式（retry）

```
INFO:auto_deployer.workflow:Auto mode enabled - using AutoRetryHandler
INFO:auto_deployer.interaction.handler:🤖 Using AutoRetryHandler - will trigger replanning on user interactions
INFO:auto_deployer.interaction.handler:[AUTO MODE] 🔄 Interaction requested: Select port
INFO:auto_deployer.interaction.handler:[AUTO MODE] 🔄 Returning 'retry' to trigger replanning
```

### CLI 交互模式

```
🤔 Agent 需要您的输入:
   选择应用运行端口

   ℹ️  检测到 package.json 中未指定端口

   选项:
   [1] 3000 (默认)
   [2] 8080
   [3] 5000
   [0] 自定义输入 (您可以输入自己的指令或值)

   请选择 [1]:
```

## 向后兼容性

- ✅ 完全向后兼容
- ✅ 默认行为保持不变（CLI 模式）
- ✅ 可手动传入 `interaction_handler` 参数覆盖自动选择
- ✅ 所有现有代码无需修改

## 测试验证

运行以下代码验证功能：

```python
import sys
sys.path.insert(0, 'src')

from auto_deployer.config import load_config
from auto_deployer.interaction import AutoRetryHandler, InteractionRequest, InputType

# 测试配置加载
config = load_config()
print(f"Mode: {config.interaction.mode}")

# 测试 AutoRetryHandler
handler = AutoRetryHandler()
request = InteractionRequest(
    question="Test question",
    input_type=InputType.TEXT
)
response = handler.ask(request)
print(f"Response: {response.value}")  # 输出: retry
print(f"Metadata: {response.metadata}")  # 输出: {'auto_retry': True, ...}
```

## 命令行帮助

```bash
auto-deployer deploy --help
```

新增参数:

```
  --non-interactive     Disable user interaction (auto-retry on interaction requests)
  --auto-mode {retry,defaults}
                        Auto mode behavior: 'retry' triggers replanning, 'defaults' uses default values
```
