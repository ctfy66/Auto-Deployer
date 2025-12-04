# SSH 模块

SSH 远程会话管理模块。

**模块路径**：`auto_deployer.ssh`

---

## 概述

`ssh` 模块提供 SSH 连接和命令执行功能，基于 Paramiko 库实现。支持密码和密钥认证，自动处理 sudo 命令，支持实时输出流。

---

## 异常

### SSHConnectionError

SSH 连接失败时抛出的异常。

```python
class SSHConnectionError(RuntimeError):
    pass
```

#### 常见原因

- 网络不可达
- 认证失败（密码错误或密钥无效）
- 主机密钥验证失败
- 连接超时

#### 处理示例

```python
from auto_deployer.ssh import SSHSession, SSHCredentials, SSHConnectionError

try:
    session = SSHSession(credentials)
    session.connect()
except SSHConnectionError as e:
    print(f"SSH 连接失败: {e}")
    # 处理错误...
```

---

## 类

### SSHCredentials

SSH 凭据数据类。

```python
@dataclass
class SSHCredentials:
    host: str
    port: int = 22
    username: str = ""
    auth_method: str = "password"
    password: Optional[str] = None
    key_path: Optional[str] = None
    passphrase: Optional[str] = None
    timeout: int = 30
```

#### 属性

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `host` | `str` | - | 目标主机地址 |
| `port` | `int` | `22` | SSH 端口 |
| `username` | `str` | `""` | 用户名 |
| `auth_method` | `str` | `"password"` | 认证方式：`"password"` 或 `"key"` |
| `password` | `Optional[str]` | `None` | 密码（密码认证时使用） |
| `key_path` | `Optional[str]` | `None` | 私钥文件路径（密钥认证时使用） |
| `passphrase` | `Optional[str]` | `None` | 私钥密码（如果私钥有密码保护） |
| `timeout` | `int` | `30` | 连接超时时间（秒） |

#### 方法

##### validate

验证凭据是否完整有效。

```python
def validate(self) -> None
```

如果凭据无效，抛出 `ValueError`。

#### 示例

```python
from auto_deployer.ssh import SSHCredentials

# 密码认证
creds = SSHCredentials(
    host="192.168.1.100",
    port=22,
    username="deploy",
    auth_method="password",
    password="secret123",
)

# 密钥认证
creds = SSHCredentials(
    host="production.example.com",
    username="ubuntu",
    auth_method="key",
    key_path="/home/user/.ssh/id_rsa",
    passphrase="key-password",  # 可选
)

# 验证
creds.validate()  # 如果无效会抛出 ValueError
```

---

### SSHCommandResult

SSH 命令执行结果数据类。

```python
@dataclass
class SSHCommandResult:
    command: str
    stdout: str
    stderr: str
    exit_status: int
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `command` | `str` | 执行的命令 |
| `stdout` | `str` | 标准输出 |
| `stderr` | `str` | 标准错误 |
| `exit_status` | `int` | 退出码 |

#### 属性方法

##### ok

检查命令是否成功执行。

```python
@property
def ok(self) -> bool
```

**返回**：`exit_status == 0`

#### 示例

```python
result = session.run("ls -la")

if result.ok:
    print("命令成功")
    print(result.stdout)
else:
    print(f"命令失败，退出码: {result.exit_status}")
    print(result.stderr)
```

---

### SSHSession

SSH 会话管理类。

```python
class SSHSession:
    def __init__(
        self,
        credentials: SSHCredentials,
        *,
        client_factory: Optional[Callable[[], paramiko.SSHClient]] = None,
    ) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `credentials` | `SSHCredentials` | SSH 凭据 |
| `client_factory` | `Optional[Callable]` | Paramiko 客户端工厂（用于测试） |

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `credentials` | `SSHCredentials` | SSH 凭据 |
| `sudo_password` | `Optional[str]` | sudo 密码（与 SSH 密码相同） |

#### 方法

##### connect

建立 SSH 连接。

```python
def connect(self) -> None
```

如果连接失败，抛出 `SSHConnectionError`。

##### close

关闭 SSH 连接。

```python
def close(self) -> None
```

##### run

在远程服务器执行命令。

```python
def run(
    self,
    command: str,
    *,
    timeout: Optional[int] = None,
    stream_output: bool = True,
) -> SSHCommandResult
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `command` | `str` | - | 要执行的命令 |
| `timeout` | `Optional[int]` | `None` | 命令超时时间（秒） |
| `stream_output` | `bool` | `True` | 是否实时输出到控制台 |

**返回**：`SSHCommandResult`

**特性**：
- 自动加载 `~/.nvm/nvm.sh` 和 `~/.bashrc`
- 自动处理 sudo 命令（通过 stdin 传递密码）
- 支持实时输出流

---

## 上下文管理器支持

`SSHSession` 支持 with 语句：

```python
from auto_deployer.ssh import SSHSession, SSHCredentials

creds = SSHCredentials(...)

with SSHSession(creds) as session:
    result = session.run("uname -a")
    print(result.stdout)
# 自动关闭连接
```

---

## sudo 命令自动处理

`SSHSession` 会自动检测 sudo 命令并通过 stdin 传递密码：

```python
# 原始命令
session.run("sudo apt update")

# 实际执行的命令
# sudo -S apt update
# (密码通过 stdin 传递)
```

**注意事项**：
- sudo 密码与 SSH 密码相同（`credentials.password`）
- 避免在同一命令中混合 sudo 和需要 stdin 的操作（如 heredoc）

---

## RemoteProbe

远程主机信息探测器。

```python
class RemoteProbe:
    def collect(self, session: SSHSession) -> RemoteHostFacts: ...
```

#### 方法

##### collect

收集远程主机信息。

```python
def collect(self, session: SSHSession) -> RemoteHostFacts
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `session` | `SSHSession` | 已连接的 SSH 会话 |

**返回**：`RemoteHostFacts`

---

### RemoteHostFacts

远程主机信息数据类。

```python
@dataclass
class RemoteHostFacts:
    hostname: str
    os_release: str
    kernel: str
    architecture: str
    has_docker: bool
    has_git: bool
    has_node: bool
    has_python3: bool
    # ... 更多字段
```

#### 主要属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `hostname` | `str` | 主机名 |
| `os_release` | `str` | 操作系统版本（如 "Ubuntu 22.04"） |
| `kernel` | `str` | 内核版本 |
| `architecture` | `str` | 架构（如 "x86_64"） |
| `has_docker` | `bool` | 是否安装 Docker |
| `has_git` | `bool` | 是否安装 Git |
| `has_node` | `bool` | 是否安装 Node.js |
| `has_python3` | `bool` | 是否安装 Python 3 |

#### 方法

##### to_payload

转换为字典格式（用于 Prompt）。

```python
def to_payload(self) -> Dict[str, Any]
```

---

## 使用示例

### 基本用法

```python
from auto_deployer.ssh import SSHSession, SSHCredentials

# 创建凭据
creds = SSHCredentials(
    host="192.168.1.100",
    username="deploy",
    auth_method="password",
    password="secret123",
)

# 建立连接
session = SSHSession(creds)
session.connect()

try:
    # 执行命令
    result = session.run("pwd")
    print(f"当前目录: {result.stdout}")
    
    # 执行多个命令
    session.run("cd /var/www && ls -la")
    
    # 带 sudo 的命令
    session.run("sudo apt update")
    
finally:
    session.close()
```

### 使用 with 语句

```python
with SSHSession(creds) as session:
    # 探测主机信息
    from auto_deployer.ssh import RemoteProbe
    
    probe = RemoteProbe()
    facts = probe.collect(session)
    
    print(f"主机: {facts.hostname}")
    print(f"系统: {facts.os_release}")
    print(f"Docker: {'✓' if facts.has_docker else '✗'}")
```

### 不使用实时输出

```python
# 禁用实时输出（适合程序化使用）
result = session.run("npm install", stream_output=False)
print(result.stdout)
```

### 设置命令超时

```python
# 设置 5 分钟超时
result = session.run("npm run build", timeout=300)
```

### 错误处理

```python
from auto_deployer.ssh import SSHConnectionError

try:
    session = SSHSession(creds)
    session.connect()
    
    result = session.run("some-command")
    if not result.ok:
        print(f"命令失败: {result.stderr}")
        
except SSHConnectionError as e:
    print(f"连接失败: {e}")
except Exception as e:
    print(f"其他错误: {e}")
finally:
    session.close()
```

---

## 相关文档

- [workflow](workflow.md) - 工作流中使用 SSHSession
- [agent](agent.md) - Agent 使用 SSHSession 执行命令
- [local](local.md) - 本地会话（类似接口）

