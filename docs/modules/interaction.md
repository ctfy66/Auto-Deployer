# Interaction 模块

用户交互处理模块。

**模块路径**：`auto_deployer.interaction`

---

## 概述

`interaction` 模块提供 Agent 与用户交互的抽象层。通过定义统一的请求/响应模型和可插拔的处理器，支持 CLI、GUI、Web 等多种交互方式。

---

## 枚举

### InputType

用户输入类型枚举。

```python
class InputType(str, Enum):
    CHOICE = "choice"    # 选择题，从选项中选择
    TEXT = "text"        # 自由文本输入
    CONFIRM = "confirm"  # 是/否确认
    SECRET = "secret"    # 敏感信息（密码等，输入时不显示）
```

### QuestionCategory

问题分类枚举。

```python
class QuestionCategory(str, Enum):
    DECISION = "decision"           # 部署决策（选择端口、入口点等）
    CONFIRMATION = "confirmation"   # 确认高风险操作
    INFORMATION = "information"     # 需要额外信息（环境变量等）
    ERROR_RECOVERY = "error_recovery"  # 错误恢复选项
    CUSTOM = "custom"               # 自定义问题
```

---

## 类

### InteractionRequest

Agent 向用户发起的交互请求。

```python
@dataclass
class InteractionRequest:
    question: str
    input_type: InputType = InputType.CHOICE
    options: List[str] = field(default_factory=list)
    category: QuestionCategory = QuestionCategory.DECISION
    context: Optional[str] = None
    default: Optional[str] = None
    allow_custom: bool = True
    timeout: Optional[int] = None
```

#### 属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `question` | `str` | - | 主要问题 |
| `input_type` | `InputType` | `CHOICE` | 输入类型 |
| `options` | `List[str]` | `[]` | 可选项（用于 CHOICE 类型） |
| `category` | `QuestionCategory` | `DECISION` | 问题分类 |
| `context` | `Optional[str]` | `None` | 附加上下文信息 |
| `default` | `Optional[str]` | `None` | 默认选项 |
| `allow_custom` | `bool` | `True` | 是否允许自定义输入（CHOICE 类型） |
| `timeout` | `Optional[int]` | `None` | 超时时间（秒），None 表示无限等待 |

#### 方法

##### format_prompt

将请求格式化为用户友好的提示文本。

```python
def format_prompt(self) -> str
```

**返回**：格式化的提示字符串。

#### 示例

```python
from auto_deployer.interaction import InteractionRequest, InputType, QuestionCategory

# 选择题
request = InteractionRequest(
    question="选择应用运行端口",
    input_type=InputType.CHOICE,
    options=["3000", "8080", "5000"],
    category=QuestionCategory.DECISION,
    default="3000",
    context="检测到 package.json 中未指定端口",
)

# 确认操作
request = InteractionRequest(
    question="是否删除现有部署目录?",
    input_type=InputType.CONFIRM,
    category=QuestionCategory.CONFIRMATION,
    default="n",
    context="目录 ~/myapp 已存在",
)

# 文本输入
request = InteractionRequest(
    question="请输入数据库连接字符串",
    input_type=InputType.TEXT,
    category=QuestionCategory.INFORMATION,
)

# 敏感信息
request = InteractionRequest(
    question="请输入 API 密钥",
    input_type=InputType.SECRET,
    category=QuestionCategory.INFORMATION,
)
```

---

### InteractionResponse

用户对交互请求的响应。

```python
@dataclass
class InteractionResponse:
    value: str
    selected_option: Optional[int] = None
    is_custom: bool = False
    cancelled: bool = False
    timed_out: bool = False
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `value` | `str` | 用户输入的值 |
| `selected_option` | `Optional[int]` | 选择的选项索引（1-based），0 表示自定义 |
| `is_custom` | `bool` | 是否是自定义输入 |
| `cancelled` | `bool` | 用户是否取消（如按 Ctrl+C） |
| `timed_out` | `bool` | 是否超时 |

#### 类方法

##### from_choice

从选项选择创建响应。

```python
@classmethod
def from_choice(cls, option_index: int, options: List[str]) -> InteractionResponse
```

##### cancelled_response

创建取消响应。

```python
@classmethod
def cancelled_response(cls) -> InteractionResponse
```

##### timeout_response

创建超时响应。

```python
@classmethod
def timeout_response(cls) -> InteractionResponse
```

---

### UserInteractionHandler (ABC)

用户交互处理器抽象基类。

```python
class UserInteractionHandler(ABC):
    @abstractmethod
    def ask(self, request: InteractionRequest) -> InteractionResponse: ...
    
    @abstractmethod
    def notify(self, message: str, level: str = "info") -> None: ...
```

#### 抽象方法

##### ask

向用户提问并获取响应。

```python
@abstractmethod
def ask(self, request: InteractionRequest) -> InteractionResponse
```

##### notify

向用户发送通知（无需响应）。

```python
@abstractmethod
def notify(self, message: str, level: str = "info") -> None
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `message` | `str` | 通知消息 |
| `level` | `str` | 级别：`"info"`、`"warning"`、`"error"`、`"success"` |

---

### CLIInteractionHandler

命令行交互处理器（默认实现）。

```python
class CLIInteractionHandler(UserInteractionHandler):
    def __init__(self, use_rich: bool = True) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_rich` | `bool` | `True` | 是否使用 rich 库增强格式化 |

#### 特性

- 支持选择题、确认、文本输入、密码输入
- 支持自定义输入（选择 0 输入自定义值）
- 支持默认值
- 按 Ctrl+C 取消操作

#### CLI 交互示例

```
🤔 Agent 需要您的输入:
   选择应用运行端口

   ℹ️  检测到 package.json 中未指定端口

   选项:
   [1] 3000 (默认)
   [2] 8080
   [3] 5000
   [0] 输入自定义命令/值

   请选择 [1]: 
```

---

### CallbackInteractionHandler

回调式交互处理器，适用于 GUI 或 Web 集成。

```python
class CallbackInteractionHandler(UserInteractionHandler):
    def __init__(
        self,
        ask_callback: Callable[[InteractionRequest], InteractionResponse],
        notify_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `ask_callback` | `Callable` | 处理用户提问的回调函数 |
| `notify_callback` | `Optional[Callable]` | 处理通知的回调函数 |

#### 示例：Web 集成

```python
from auto_deployer.interaction import CallbackInteractionHandler, InteractionResponse

# 假设有一个 WebSocket 连接
async def ask_via_websocket(request):
    # 发送问题到前端
    await websocket.send({
        "type": "question",
        "question": request.question,
        "options": request.options,
    })
    
    # 等待用户响应
    response = await websocket.receive()
    return InteractionResponse(value=response["value"])

handler = CallbackInteractionHandler(ask_callback=ask_via_websocket)
```

#### 示例：GUI 集成

```python
import tkinter as tk
from tkinter import simpledialog

def ask_via_dialog(request):
    root = tk.Tk()
    root.withdraw()
    
    if request.input_type == InputType.CHOICE:
        # 显示选择对话框
        result = simpledialog.askstring("选择", request.question)
    elif request.input_type == InputType.CONFIRM:
        # 显示确认对话框
        from tkinter import messagebox
        result = "yes" if messagebox.askyesno("确认", request.question) else "no"
    else:
        result = simpledialog.askstring("输入", request.question)
    
    root.destroy()
    return InteractionResponse(value=result or "")

handler = CallbackInteractionHandler(ask_callback=ask_via_dialog)
```

---

### AutoResponseHandler

自动响应处理器，适用于测试或非交互模式。

```python
class AutoResponseHandler(UserInteractionHandler):
    def __init__(
        self,
        default_responses: Optional[dict] = None,
        always_confirm: bool = True,
        use_defaults: bool = True,
    ) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `default_responses` | `Optional[dict]` | `None` | 问题关键词到响应的映射 |
| `always_confirm` | `bool` | `True` | 是否自动确认（True）或拒绝（False） |
| `use_defaults` | `bool` | `True` | 是否使用请求中的默认值 |

#### 响应优先级

1. 检查 `default_responses` 中是否有匹配的关键词
2. 使用请求中的 `default` 值
3. CONFIRM 类型：根据 `always_confirm` 返回 yes/no
4. CHOICE 类型：选择第一个选项
5. 其他类型：返回空字符串

#### 示例：CI/CD 环境

```python
from auto_deployer.interaction import AutoResponseHandler

# 预设响应
handler = AutoResponseHandler(
    default_responses={
        "port": "3000",
        "database": "postgresql",
        "环境": "production",
    },
    always_confirm=True,  # 自动确认所有操作
    use_defaults=True,
)

# 使用
workflow = DeploymentWorkflow(
    config=config,
    workspace=workspace,
    interaction_handler=handler,
)
```

#### 示例：测试

```python
# 拒绝所有确认操作（安全模式）
handler = AutoResponseHandler(always_confirm=False)

# 总是使用第一个选项
handler = AutoResponseHandler(use_defaults=False)
```

---

## 使用示例

### 自定义处理器

```python
from auto_deployer.interaction import (
    UserInteractionHandler,
    InteractionRequest,
    InteractionResponse,
)

class LoggingHandler(UserInteractionHandler):
    """记录所有交互的处理器"""
    
    def __init__(self, inner_handler):
        self.inner = inner_handler
        self.interactions = []
    
    def ask(self, request):
        response = self.inner.ask(request)
        self.interactions.append({
            "question": request.question,
            "response": response.value,
        })
        return response
    
    def notify(self, message, level="info"):
        self.interactions.append({
            "notification": message,
            "level": level,
        })
        self.inner.notify(message, level)
```

### 在工作流中使用

```python
from auto_deployer.workflow import DeploymentWorkflow
from auto_deployer.interaction import CLIInteractionHandler

# 使用 CLI 处理器（默认）
workflow = DeploymentWorkflow(
    config=config,
    workspace=workspace,
    interaction_handler=CLIInteractionHandler(),
)

# 部署时，Agent 可能会询问用户：
# - 选择端口
# - 确认删除操作
# - 输入环境变量
```

### 直接创建请求

```python
from auto_deployer.interaction import (
    InteractionRequest,
    CLIInteractionHandler,
    InputType,
)

handler = CLIInteractionHandler()

# 创建请求
request = InteractionRequest(
    question="选择部署环境",
    input_type=InputType.CHOICE,
    options=["development", "staging", "production"],
    default="development",
)

# 获取用户响应
response = handler.ask(request)
print(f"用户选择: {response.value}")
```

---

## 相关文档

- [workflow](workflow.md) - 在工作流中注入交互处理器
- [agent](agent.md) - Agent 使用交互处理器与用户沟通

