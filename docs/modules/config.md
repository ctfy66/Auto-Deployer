# Config 模块

配置加载与管理模块。

**模块路径**：`auto_deployer.config`

---

## 概述

`config` 模块提供应用配置的加载和管理功能。支持配置文件、环境变量和代码默认值三种配置来源，按优先级合并。

---

## 类

### LLMConfig

LLM 配置数据类。

```python
@dataclass
class LLMConfig:
    provider: str = "dummy"
    model: str = "planning-v0"
    api_key: Optional[str] = None
    endpoint: Optional[str] = None
    temperature: float = 0.0
    proxy: Optional[str] = None
```

#### 属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | `str` | `"dummy"` | LLM 提供商：`"gemini"` 或 `"openai"` |
| `model` | `str` | `"planning-v0"` | 模型名称，如 `"gemini-2.5-flash"` |
| `api_key` | `Optional[str]` | `None` | API 密钥 |
| `endpoint` | `Optional[str]` | `None` | 自定义 API 端点（用于代理或私有部署） |
| `temperature` | `float` | `0.0` | 温度参数（0.0 = 确定性输出） |
| `proxy` | `Optional[str]` | `None` | HTTP 代理，如 `"http://127.0.0.1:7890"` |

#### 示例

```python
from auto_deployer.config import LLMConfig

# Gemini 配置
llm_config = LLMConfig(
    provider="gemini",
    model="gemini-2.5-flash",
    api_key="AIzaSy...",
    temperature=0.0,
)

# OpenAI 配置
llm_config = LLMConfig(
    provider="openai",
    model="gpt-4",
    api_key="sk-...",
    temperature=0.2,
)

# 使用代理
llm_config = LLMConfig(
    provider="gemini",
    model="gemini-2.5-flash",
    api_key="...",
    proxy="http://127.0.0.1:7890",
)
```

---

### AgentConfig

Agent 配置数据类。

```python
@dataclass
class AgentConfig:
    max_iterations: int = 40
```

#### 属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_iterations` | `int` | `40` | Agent 最大迭代次数 |

---

### DeploymentConfig

部署相关配置数据类。

```python
@dataclass
class DeploymentConfig:
    workspace_root: str = ".auto-deployer/workspace"
    default_host: Optional[str] = None
    default_port: int = 22
    default_username: Optional[str] = None
    default_auth_method: Optional[str] = None
    default_password: Optional[str] = None
    default_key_path: Optional[str] = None
```

#### 属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `workspace_root` | `str` | `".auto-deployer/workspace"` | 本地仓库分析工作目录 |
| `default_host` | `Optional[str]` | `None` | 默认 SSH 主机 |
| `default_port` | `int` | `22` | 默认 SSH 端口 |
| `default_username` | `Optional[str]` | `None` | 默认 SSH 用户名 |
| `default_auth_method` | `Optional[str]` | `None` | 默认认证方式 |
| `default_password` | `Optional[str]` | `None` | 默认 SSH 密码 |
| `default_key_path` | `Optional[str]` | `None` | 默认 SSH 私钥路径 |

---

### AppConfig

顶层应用配置数据类。

```python
@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `llm` | `LLMConfig` | LLM 配置 |
| `agent` | `AgentConfig` | Agent 配置 |
| `deployment` | `DeploymentConfig` | 部署配置 |

#### 类方法

##### from_dict

从字典创建配置。

```python
@classmethod
def from_dict(cls, payload: Dict[str, Any]) -> AppConfig
```

---

## 函数

### load_config

加载配置。

```python
def load_config(path: Optional[str] = None) -> AppConfig
```

#### 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `path` | `Optional[str]` | 配置文件路径，默认为 `config/default_config.json` |

#### 返回

`AppConfig` 实例。

#### 异常

- `FileNotFoundError`：配置文件不存在

---

## 配置优先级

配置按以下优先级加载（高优先级覆盖低优先级）：

```
1. 环境变量           (最高)
   ↓
2. 配置文件 (JSON)
   ↓
3. 代码默认值         (最低)
```

### 环境变量映射

| 环境变量 | 配置项 |
|----------|--------|
| `AUTO_DEPLOYER_GEMINI_API_KEY` | `llm.api_key`（provider=gemini） |
| `AUTO_DEPLOYER_OPENAI_API_KEY` | `llm.api_key`（provider=openai） |
| `AUTO_DEPLOYER_LLM_API_KEY` | `llm.api_key`（通用） |
| `AUTO_DEPLOYER_LLM_PROXY` | `llm.proxy` |
| `AUTO_DEPLOYER_SSH_HOST` | `deployment.default_host` |
| `AUTO_DEPLOYER_SSH_PORT` | `deployment.default_port` |
| `AUTO_DEPLOYER_SSH_USERNAME` | `deployment.default_username` |
| `AUTO_DEPLOYER_SSH_PASSWORD` | `deployment.default_password` |
| `AUTO_DEPLOYER_SSH_KEY_PATH` | `deployment.default_key_path` |

---

## 配置文件格式

`config/default_config.json`：

```json
{
  "llm": {
    "provider": "gemini",
    "model": "gemini-2.5-flash",
    "api_key": null,
    "endpoint": null,
    "temperature": 0.0,
    "proxy": null
  },
  "agent": {
    "max_iterations": 40
  },
  "deployment": {
    "workspace_root": ".auto-deployer/workspace",
    "default_host": null,
    "default_port": 22,
    "default_username": null,
    "default_auth_method": null,
    "default_password": null,
    "default_key_path": null
  }
}
```

---

## 使用示例

### 加载默认配置

```python
from auto_deployer import load_config

config = load_config()
print(f"LLM Provider: {config.llm.provider}")
print(f"Model: {config.llm.model}")
```

### 加载自定义配置文件

```python
config = load_config("my_config.json")
```

### 程序化创建配置

```python
from auto_deployer.config import AppConfig, LLMConfig, AgentConfig, DeploymentConfig

config = AppConfig(
    llm=LLMConfig(
        provider="gemini",
        model="gemini-2.5-flash",
        api_key="your-api-key",
    ),
    agent=AgentConfig(
        max_iterations=50,
    ),
    deployment=DeploymentConfig(
        default_host="192.168.1.100",
        default_username="deploy",
    ),
)
```

### 从字典创建

```python
config_dict = {
    "llm": {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "api_key": "...",
    },
    "agent": {
        "max_iterations": 30,
    },
}

config = AppConfig.from_dict(config_dict)
```

### 结合环境变量

```python
import os

# 设置环境变量
os.environ["AUTO_DEPLOYER_GEMINI_API_KEY"] = "your-api-key"
os.environ["AUTO_DEPLOYER_SSH_HOST"] = "192.168.1.100"

# 加载配置（会自动读取环境变量）
config = load_config()

print(config.llm.api_key)  # your-api-key
print(config.deployment.default_host)  # 192.168.1.100
```

### 使用 .env 文件

创建 `.env` 文件：

```bash
AUTO_DEPLOYER_GEMINI_API_KEY=AIzaSy...
AUTO_DEPLOYER_SSH_HOST=192.168.1.100
AUTO_DEPLOYER_SSH_USERNAME=deploy
AUTO_DEPLOYER_SSH_PASSWORD=secret
```

```python
# load_config 会自动加载 .env 文件
config = load_config()
```

### 检查配置有效性

```python
config = load_config()

# 检查 LLM API Key
if not config.llm.api_key:
    raise ValueError("请设置 AUTO_DEPLOYER_GEMINI_API_KEY 环境变量")

# 检查 SSH 配置
if not config.deployment.default_host:
    print("警告：未设置默认 SSH 主机，需要在命令行指定")
```

---

## 相关文档

- [workflow](workflow.md) - 使用 AppConfig
- [agent](agent.md) - 使用 LLMConfig
- [CLI 参考](../cli-reference.md) - CLI 配置选项

