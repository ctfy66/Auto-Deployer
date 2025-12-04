# Workflow 模块

高层部署工作流编排模块。

**模块路径**：`auto_deployer.workflow`

---

## 概述

`workflow` 模块提供部署流程的高层抽象，协调仓库分析、连接建立和 Agent 部署三个阶段。是使用 Auto-Deployer 的推荐入口。

---

## 类

### DeploymentRequest

SSH 远程部署请求的数据类。

```python
@dataclass
class DeploymentRequest:
    repo_url: str
    host: str
    port: int
    username: str
    auth_method: str
    password: Optional[str]
    key_path: Optional[str]
    deploy_dir: Optional[str] = None
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `repo_url` | `str` | Git 仓库 URL（支持 SSH 和 HTTPS 格式） |
| `host` | `str` | 目标服务器地址 |
| `port` | `int` | SSH 端口号 |
| `username` | `str` | SSH 用户名 |
| `auth_method` | `str` | 认证方式：`"password"` 或 `"key"` |
| `password` | `Optional[str]` | SSH 密码（密码认证时必需） |
| `key_path` | `Optional[str]` | SSH 私钥路径（密钥认证时必需） |
| `deploy_dir` | `Optional[str]` | 目标部署目录，默认为 `~/<repo_name>` |

#### 示例

```python
from auto_deployer.workflow import DeploymentRequest

# 密码认证
request = DeploymentRequest(
    repo_url="git@github.com:user/myapp.git",
    host="192.168.1.100",
    port=22,
    username="deploy",
    auth_method="password",
    password="secret123",
    key_path=None,
    deploy_dir="/var/www/myapp",
)

# 密钥认证
request = DeploymentRequest(
    repo_url="https://github.com/user/myapp.git",
    host="production.example.com",
    port=22,
    username="ubuntu",
    auth_method="key",
    password=None,
    key_path="~/.ssh/id_rsa",
)
```

---

### LocalDeploymentRequest

本地部署请求的数据类。

```python
@dataclass
class LocalDeploymentRequest:
    repo_url: str
    deploy_dir: Optional[str] = None
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `repo_url` | `str` | Git 仓库 URL |
| `deploy_dir` | `Optional[str]` | 本地部署目录，默认为 `~/<repo_name>` |

#### 示例

```python
from auto_deployer.workflow import LocalDeploymentRequest

request = LocalDeploymentRequest(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="D:/Projects/myapp",  # Windows 路径
)
```

---

### DeploymentWorkflow

部署工作流编排器，协调整个部署流程。

```python
class DeploymentWorkflow:
    def __init__(
        self,
        config: AppConfig,
        workspace: str,
        interaction_handler: Optional[UserInteractionHandler] = None,
    ) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `AppConfig` | 应用配置（包含 LLM、Agent、部署配置） |
| `workspace` | `str` | 本地工作目录（用于克隆仓库进行分析） |
| `interaction_handler` | `Optional[UserInteractionHandler]` | 用户交互处理器，默认使用 `CLIInteractionHandler` |

#### 方法

##### run_deploy

运行 SSH 远程部署工作流。

```python
def run_deploy(self, request: DeploymentRequest) -> None
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `request` | `DeploymentRequest` | 部署请求 |

**工作流程**：

1. 克隆仓库到本地，分析项目结构
2. 建立 SSH 连接，探测远程主机信息
3. 创建 Agent，运行部署循环
4. 关闭 SSH 连接

##### run_local_deploy

运行本地部署工作流。

```python
def run_local_deploy(self, request: LocalDeploymentRequest) -> None
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `request` | `LocalDeploymentRequest` | 本地部署请求 |

**工作流程**：

1. 克隆仓库到本地，分析项目结构
2. 探测本地主机信息
3. 创建本地 Session 和 Agent，运行部署循环

---

## 使用示例

### 基本用法

```python
from auto_deployer import load_config
from auto_deployer.workflow import DeploymentWorkflow, DeploymentRequest

# 加载配置
config = load_config("config/default_config.json")

# 创建工作流
workflow = DeploymentWorkflow(
    config=config,
    workspace=".auto-deployer/workspace",
)

# 创建部署请求
request = DeploymentRequest(
    repo_url="git@github.com:myorg/myapp.git",
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

### 使用自定义交互处理器

```python
from auto_deployer.workflow import DeploymentWorkflow
from auto_deployer.interaction import AutoResponseHandler

# 自动响应处理器（用于 CI/CD 环境）
auto_handler = AutoResponseHandler(
    default_responses={
        "port": "3000",
        "database": "postgresql",
    },
    always_confirm=True,
)

workflow = DeploymentWorkflow(
    config=config,
    workspace=workspace,
    interaction_handler=auto_handler,
)
```

### 本地部署

```python
from auto_deployer.workflow import DeploymentWorkflow, LocalDeploymentRequest

workflow = DeploymentWorkflow(config=config, workspace=workspace)

request = LocalDeploymentRequest(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/projects/myapp",
)

workflow.run_local_deploy(request)
```

### 捕获部署结果

```python
import logging

# 配置日志以查看部署过程
logging.basicConfig(level=logging.INFO)

try:
    workflow.run_deploy(request)
    print("部署成功！")
except Exception as e:
    print(f"部署失败: {e}")

# 部署结果会保存在 agent_logs/ 目录下
```

---

## 相关文档

- [config](config.md) - 配置类 `AppConfig`
- [agent](agent.md) - Agent 实现细节
- [interaction](interaction.md) - 交互处理器

