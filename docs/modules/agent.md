# Agent 模块

LLM 驱动的自主部署 Agent。

**模块路径**：`auto_deployer.llm.agent`

---

## 概述

`agent` 模块是 Auto-Deployer 的核心，实现了基于 LLM 的自主决策循环。Agent 通过与 LLM API 交互，分析当前状态并决定下一步操作，直到部署完成或失败。

---

## 类

### AgentAction

Agent 决策的动作数据类。

```python
@dataclass
class AgentAction:
    action_type: str
    command: Optional[str] = None
    reasoning: Optional[str] = None
    message: Optional[str] = None
    question: Optional[str] = None
    options: Optional[List[str]] = None
    input_type: str = "choice"
    category: str = "decision"
    context: Optional[str] = None
    default_option: Optional[str] = None
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `action_type` | `str` | 动作类型：`"execute"`、`"done"`、`"failed"`、`"ask_user"` |
| `command` | `Optional[str]` | 要执行的命令（`execute` 时使用） |
| `reasoning` | `Optional[str]` | LLM 的推理说明 |
| `message` | `Optional[str]` | 完成/失败消息 |
| `question` | `Optional[str]` | 要问用户的问题（`ask_user` 时使用） |
| `options` | `Optional[List[str]]` | 用户可选项 |
| `input_type` | `str` | 输入类型：`"choice"`、`"text"`、`"confirm"`、`"secret"` |
| `category` | `str` | 问题分类：`"decision"`、`"confirmation"`、`"information"`、`"error_recovery"` |
| `context` | `Optional[str]` | 附加上下文信息 |
| `default_option` | `Optional[str]` | 默认选项 |

#### 动作类型说明

| 类型 | 说明 | 必需字段 |
|------|------|----------|
| `execute` | 执行 Shell 命令 | `command` |
| `done` | 部署成功完成 | `message` |
| `failed` | 部署失败放弃 | `message` |
| `ask_user` | 询问用户输入 | `question` |

#### LLM 响应示例

```json
// 执行命令
{"action": "execute", "command": "npm install", "reasoning": "安装项目依赖"}

// 询问用户
{"action": "ask_user", "question": "选择应用端口?", "options": ["3000", "8080", "5000"], "input_type": "choice"}

// 部署完成
{"action": "done", "message": "应用已部署到 http://192.168.1.100:3000"}

// 部署失败
{"action": "failed", "message": "缺少必要的数据库配置，无法继续"}
```

---

### CommandResult

命令执行结果数据类。

```python
@dataclass
class CommandResult:
    command: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `command` | `str` | 执行的命令 |
| `success` | `bool` | 是否成功（`exit_code == 0`） |
| `stdout` | `str` | 标准输出 |
| `stderr` | `str` | 标准错误 |
| `exit_code` | `int` | 退出码 |

---

### DeploymentAgent

LLM 驱动的自主部署 Agent。

```python
class DeploymentAgent:
    def __init__(
        self,
        config: LLMConfig,
        max_iterations: int = 30,
        log_dir: Optional[str] = None,
        interaction_handler: Optional[UserInteractionHandler] = None,
        experience_retriever: Optional[ExperienceRetriever] = None,
    ) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `LLMConfig` | LLM 配置（必须包含 `api_key`） |
| `max_iterations` | `int` | 最大迭代次数，默认 30 |
| `log_dir` | `Optional[str]` | 日志目录，默认 `./agent_logs` |
| `interaction_handler` | `Optional[UserInteractionHandler]` | 用户交互处理器 |
| `experience_retriever` | `Optional[ExperienceRetriever]` | 经验检索器 |

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `config` | `LLMConfig` | LLM 配置 |
| `max_iterations` | `int` | 最大迭代次数 |
| `history` | `List[dict]` | 命令执行历史 |
| `user_interactions` | `List[dict]` | 用户交互历史 |
| `current_log_file` | `Optional[Path]` | 当前日志文件路径 |

#### 方法

##### deploy

运行 SSH 远程自主部署循环。

```python
def deploy(
    self,
    request: DeploymentRequest,
    host_facts: Optional[RemoteHostFacts],
    ssh_session: SSHSession,
    repo_context: Optional[RepoContext] = None,
) -> bool
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `request` | `DeploymentRequest` | 部署请求 |
| `host_facts` | `Optional[RemoteHostFacts]` | 远程主机信息 |
| `ssh_session` | `SSHSession` | 活跃的 SSH 会话 |
| `repo_context` | `Optional[RepoContext]` | 预分析的仓库上下文 |

**返回**：`True` 表示部署成功，`False` 表示失败。

##### deploy_local

运行本地自主部署循环。

```python
def deploy_local(
    self,
    request: LocalDeploymentRequest,
    host_facts: Optional[LocalHostFacts],
    local_session: LocalSession,
    repo_context: Optional[RepoContext] = None,
) -> bool
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `request` | `LocalDeploymentRequest` | 本地部署请求 |
| `host_facts` | `Optional[LocalHostFacts]` | 本地主机信息 |
| `local_session` | `LocalSession` | 本地命令执行会话 |
| `repo_context` | `Optional[RepoContext]` | 预分析的仓库上下文 |

**返回**：`True` 表示部署成功，`False` 表示失败。

---

## Agent 循环详解

```
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Main Loop                               │
│                                                                 │
│  for iteration in 1..max_iterations:                            │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. 构建 Prompt                                           │   │
│  │    - 系统提示（角色定义、可用动作、最佳实践）              │   │
│  │    - 仓库上下文（项目类型、框架、关键文件）               │   │
│  │    - 主机信息（OS、已安装工具）                          │   │
│  │    - 历史经验（从知识库检索）                            │   │
│  │    - 命令历史（已执行命令及结果）                        │   │
│  │    - 用户交互历史                                        │   │
│  └──────────────────────────────────────────────────────────┘   │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 2. 调用 LLM API                                          │   │
│  │    - 发送 Prompt                                         │   │
│  │    - 请求 JSON 格式响应                                  │   │
│  │    - 处理速率限制（自动重试）                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 3. 解析响应为 AgentAction                                │   │
│  └──────────────────────────────────────────────────────────┘   │
│      │                                                          │
│      ▼                                                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 4. 执行动作                                              │   │
│  │                                                          │   │
│  │    if action == "execute":                               │   │
│  │        result = session.run(command)                     │   │
│  │        history.append(result)                            │   │
│  │        continue loop                                     │   │
│  │                                                          │   │
│  │    if action == "ask_user":                              │   │
│  │        response = handler.ask(question)                  │   │
│  │        if cancelled: return False                        │   │
│  │        user_interactions.append(response)                │   │
│  │        continue loop                                     │   │
│  │                                                          │   │
│  │    if action == "done":                                  │   │
│  │        log_success()                                     │   │
│  │        return True                                       │   │
│  │                                                          │   │
│  │    if action == "failed":                                │   │
│  │        log_failure()                                     │   │
│  │        return False                                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  // 达到 max_iterations                                         │
│  log_max_iterations()                                           │
│  return False                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prompt 构建策略

Agent 的 Prompt 由以下部分组成：

### 系统提示词

定义 Agent 角色和能力：
- 角色：DevOps 部署专家
- 可用动作：execute, done, failed, ask_user
- 部署策略：Docker Compose > Docker > 传统方式
- Shell 最佳实践
- 错误诊断指南

### 仓库上下文（如果有）

```
# Pre-Analyzed Repository Context
- URL: https://github.com/user/project.git
- Detected Type: nodejs
- Framework: Next.js

## Directory Structure
project/
├── package.json
├── next.config.js
└── ...

## Available Scripts
- npm run dev: next dev
- npm run build: next build
- npm start: next start

## Key Files
### package.json
{...}
```

### 当前状态

```json
{
  "repo_url": "...",
  "server": {
    "target": "user@host:22",
    "os": "Ubuntu 22.04"
  },
  "command_history": [
    {
      "iteration": 1,
      "command": "git clone ...",
      "success": true,
      "stdout": "..."
    }
  ],
  "user_interactions": [...]
}
```

---

## 使用示例

### 直接使用 Agent

```python
from auto_deployer.llm.agent import DeploymentAgent
from auto_deployer.config import LLMConfig
from auto_deployer.ssh import SSHSession, SSHCredentials

# 配置 LLM
llm_config = LLMConfig(
    provider="gemini",
    model="gemini-2.5-flash",
    api_key="your-api-key",
    temperature=0.0,
)

# 创建 Agent
agent = DeploymentAgent(
    config=llm_config,
    max_iterations=30,
    log_dir="./my_logs",
)

# 创建 SSH 会话
creds = SSHCredentials(...)
session = SSHSession(creds)
session.connect()

# 运行部署
from auto_deployer.workflow import DeploymentRequest
request = DeploymentRequest(...)

success = agent.deploy(
    request=request,
    host_facts=None,  # 可选
    ssh_session=session,
    repo_context=None,  # 可选
)

print(f"部署{'成功' if success else '失败'}")
print(f"日志文件: {agent.current_log_file}")
```

### 使用经验检索

```python
from auto_deployer.knowledge import ExperienceStore, ExperienceRetriever

# 创建经验检索器
store = ExperienceStore()
retriever = ExperienceRetriever(store)

# 注入到 Agent
agent = DeploymentAgent(
    config=llm_config,
    experience_retriever=retriever,
)
```

### 自定义交互处理

```python
from auto_deployer.interaction import CallbackInteractionHandler

def my_ask_callback(request):
    # 自定义交互逻辑（如显示 GUI 对话框）
    print(f"问题: {request.question}")
    user_input = my_gui_dialog(request.options)
    return InteractionResponse(value=user_input)

handler = CallbackInteractionHandler(ask_callback=my_ask_callback)

agent = DeploymentAgent(
    config=llm_config,
    interaction_handler=handler,
)
```

---

## 日志格式

每次部署会生成一个 JSON 日志文件：

```json
{
  "repo_url": "https://github.com/user/project.git",
  "target": "user@host:22",
  "deploy_dir": "~/project",
  "start_time": "2024-12-01T10:00:00",
  "end_time": "2024-12-01T10:05:30",
  "status": "success",
  "config": {
    "model": "gemini-2.5-flash",
    "temperature": 0.0,
    "max_iterations": 30,
    "endpoint": "..."
  },
  "context": {
    "project_type": "nodejs",
    "framework": "Next.js"
  },
  "steps": [
    {
      "iteration": 1,
      "timestamp": "2024-12-01T10:00:05",
      "action": "execute",
      "command": "git clone ...",
      "reasoning": "首先克隆仓库",
      "result": {
        "success": true,
        "exit_code": 0,
        "stdout": "Cloning into...",
        "stderr": ""
      }
    }
  ]
}
```

---

## 相关文档

- [config](config.md) - LLMConfig 配置
- [ssh](ssh.md) - SSHSession
- [local](local.md) - LocalSession
- [interaction](interaction.md) - 用户交互处理
- [knowledge](knowledge.md) - 经验检索

