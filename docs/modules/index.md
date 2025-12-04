# 模块参考

本文档提供 Auto-Deployer 内部模块的技术参考文档。

## 概述

Auto-Deployer 的模块设计遵循以下原则：

- **分层设计**：高层模块（Workflow）用于常规使用，底层模块（Session、Agent）用于高级定制
- **可扩展性**：核心组件使用抽象基类，支持自定义实现
- **类型安全**：使用 dataclass 和类型提示，支持静态类型检查

> **注意**：这些是内部模块文档，主要面向需要深入了解或二次开发的开发者。普通使用请参考 [CLI 命令参考](../cli-reference.md)。

## 快速开始

### 使用高层 API

```python
from auto_deployer import load_config
from auto_deployer.workflow import DeploymentWorkflow, DeploymentRequest

# 加载配置
config = load_config()

# 创建工作流
workflow = DeploymentWorkflow(
    config=config,
    workspace=".auto-deployer/workspace"
)

# 创建部署请求
request = DeploymentRequest(
    repo_url="https://github.com/user/project.git",
    host="192.168.1.100",
    port=22,
    username="deploy",
    auth_method="password",
    password="secret",
    key_path=None,
)

# 运行部署
workflow.run_deploy(request)
```

### 使用底层 API

```python
from auto_deployer.ssh import SSHSession, SSHCredentials
from auto_deployer.llm.agent import DeploymentAgent
from auto_deployer.config import LLMConfig

# 手动创建 SSH 会话
creds = SSHCredentials(
    host="192.168.1.100",
    username="deploy",
    auth_method="password",
    password="secret"
)
session = SSHSession(creds)
session.connect()

# 执行命令
result = session.run("uname -a")
print(result.stdout)

# 手动创建 Agent
llm_config = LLMConfig(
    provider="gemini",
    model="gemini-2.5-flash",
    api_key="your-api-key"
)
agent = DeploymentAgent(llm_config, max_iterations=30)
```

---

## 模块列表

| 模块 | 说明 | 文档 |
|------|------|------|
| `auto_deployer.workflow` | 部署工作流编排 | [workflow.md](workflow.md) |
| `auto_deployer.llm.agent` | LLM 驱动的 Agent | [agent.md](agent.md) |
| `auto_deployer.analyzer` | 仓库分析 | [analyzer.md](analyzer.md) |
| `auto_deployer.ssh` | SSH 会话管理 | [ssh.md](ssh.md) |
| `auto_deployer.local` | 本地会话管理 | [local.md](local.md) |
| `auto_deployer.interaction` | 用户交互处理 | [interaction.md](interaction.md) |
| `auto_deployer.knowledge` | 经验存储与检索 | [knowledge.md](knowledge.md) |
| `auto_deployer.config` | 配置管理 | [config.md](config.md) |

---

## 模块关系图

```
┌─────────────────────────────────────────────────────────────┐
│                    auto_deployer                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    workflow                          │   │
│  │  DeploymentWorkflow, DeploymentRequest               │   │
│  └────────────────────────┬────────────────────────────┘   │
│                           │                                 │
│           ┌───────────────┼───────────────┐                │
│           │               │               │                │
│           ▼               ▼               ▼                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  analyzer   │  │    ssh      │  │  llm.agent  │        │
│  │ RepoContext │  │ SSHSession  │  │ Deployment- │        │
│  │ RepoAnalyzer│  │ SSHCreds    │  │   Agent     │        │
│  └─────────────┘  └─────────────┘  └──────┬──────┘        │
│                                           │                │
│                   ┌───────────────────────┼───────┐       │
│                   │                       │       │       │
│                   ▼                       ▼       ▼       │
│          ┌─────────────┐         ┌─────────────────────┐  │
│          │ interaction │         │      knowledge      │  │
│          │ Handler     │         │ Store, Retriever    │  │
│          └─────────────┘         └─────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                     config                           │   │
│  │  AppConfig, LLMConfig, DeploymentConfig              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 导入约定

### 推荐导入方式

```python
# 配置
from auto_deployer import AppConfig, load_config

# 工作流（高层 API）
from auto_deployer.workflow import DeploymentWorkflow, DeploymentRequest, LocalDeploymentRequest

# Agent
from auto_deployer.llm.agent import DeploymentAgent, AgentAction, CommandResult

# 仓库分析
from auto_deployer.analyzer import RepoAnalyzer, RepoContext

# SSH
from auto_deployer.ssh import SSHSession, SSHCredentials, SSHCommandResult

# 本地会话
from auto_deployer.local import LocalSession, LocalCommandResult

# 用户交互
from auto_deployer.interaction import (
    UserInteractionHandler,
    CLIInteractionHandler,
    InteractionRequest,
    InteractionResponse,
    InputType,
    QuestionCategory,
)

# 知识库（可选依赖）
from auto_deployer.knowledge import (
    ExperienceStore,
    ExperienceExtractor,
    ExperienceRefiner,
    ExperienceRetriever,
)
```

---

## 错误处理

### 常见异常

| 异常 | 模块 | 说明 |
|------|------|------|
| `SSHConnectionError` | `ssh` | SSH 连接失败 |
| `ValueError` | `config` | 配置无效（如缺少 API Key） |
| `FileNotFoundError` | `config` | 配置文件不存在 |
| `ImportError` | `knowledge` | 缺少可选依赖 |

### 异常处理示例

```python
from auto_deployer.ssh import SSHSession, SSHCredentials, SSHConnectionError

try:
    session = SSHSession(credentials)
    session.connect()
except SSHConnectionError as e:
    print(f"SSH 连接失败: {e}")
```

---

## 版本兼容性

- Python >= 3.10
- 核心依赖：paramiko, requests, python-dotenv
- 可选依赖（knowledge 模块）：chromadb, sentence-transformers

