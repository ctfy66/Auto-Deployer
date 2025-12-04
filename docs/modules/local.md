# Local 模块

本地命令执行会话模块。

**模块路径**：`auto_deployer.local`

---

## 概述

`local` 模块提供本地命令执行功能，与 `ssh` 模块接口一致，支持 Windows (PowerShell) 和 Unix (Bash) 系统。用于本地部署模式。

---

## 类

### LocalCommandResult

本地命令执行结果数据类。

```python
@dataclass
class LocalCommandResult:
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

---

### LocalSession

本地命令执行会话。

```python
class LocalSession:
    def __init__(self, working_dir: Optional[str] = None) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `working_dir` | `Optional[str]` | 工作目录，默认为用户家目录 |

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `working_dir` | `str` | 工作目录 |
| `is_windows` | `bool` | 是否为 Windows 系统 |

#### 方法

##### connect

初始化会话（为兼容 SSHSession 接口，实际为空操作）。

```python
def connect(self) -> None
```

##### close

关闭会话（为兼容 SSHSession 接口，实际为空操作）。

```python
def close(self) -> None
```

##### run

在本地执行命令。

```python
def run(
    self,
    command: str,
    *,
    timeout: Optional[int] = None,
    stream_output: bool = True,
) -> LocalCommandResult
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `command` | `str` | - | 要执行的命令 |
| `timeout` | `Optional[int]` | `None` | 命令超时时间（秒） |
| `stream_output` | `bool` | `True` | 是否实时输出到控制台 |

**返回**：`LocalCommandResult`

---

## 上下文管理器支持

```python
with LocalSession() as session:
    result = session.run("echo hello")
    print(result.stdout)
```

---

## Windows/Linux 命令适配

`LocalSession` 会自动进行基本的命令语法转换：

| Linux 命令 | Windows (PowerShell) 等效 |
|------------|---------------------------|
| `rm -rf dir` | `Remove-Item -Recurse -Force dir` |
| `rm -r dir` | `Remove-Item -Recurse -Force dir` |
| `mkdir -p dir` | `New-Item -ItemType Directory -Force -Path dir` |
| `cat file` | `Get-Content file` |
| `ls` | `Get-ChildItem` |
| `pwd` | `(Get-Location).Path` |
| `which cmd` | `Get-Command cmd` |
| `~/` | 用户家目录完整路径 |

**注意**：复杂的命令转换由 LLM Agent 处理，`LocalSession` 只做基本转换。

---

## LocalProbe

本地主机信息探测器。

```python
class LocalProbe:
    def collect(self) -> LocalHostFacts: ...
```

#### 方法

##### collect

收集本地主机信息。

```python
def collect(self) -> LocalHostFacts
```

**返回**：`LocalHostFacts`

---

### LocalHostFacts

本地主机信息数据类。

```python
@dataclass
class LocalHostFacts:
    hostname: str
    os_name: str
    os_release: str
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
| `os_name` | `str` | 操作系统名称（Windows/Linux/Darwin） |
| `os_release` | `str` | 操作系统版本 |
| `architecture` | `str` | 架构（如 AMD64） |
| `has_docker` | `bool` | 是否安装 Docker |
| `has_git` | `bool` | 是否安装 Git |
| `has_node` | `bool` | 是否安装 Node.js |
| `has_python3` | `bool` | 是否安装 Python 3 |

#### 方法

##### to_payload

转换为字典格式。

```python
def to_payload(self) -> Dict[str, Any]
```

---

## 使用示例

### 基本用法

```python
from auto_deployer.local import LocalSession

session = LocalSession()
session.connect()

try:
    # 执行命令
    result = session.run("echo Hello World")
    print(result.stdout)  # Hello World
    
    # 检查结果
    if result.ok:
        print("命令成功")
    
finally:
    session.close()
```

### 使用 with 语句

```python
with LocalSession() as session:
    result = session.run("python --version")
    print(result.stdout)
```

### 指定工作目录

```python
# 在指定目录执行命令
session = LocalSession(working_dir="D:/Projects/myapp")

with session:
    result = session.run("npm install")
```

### 探测本地环境

```python
from auto_deployer.local import LocalProbe

probe = LocalProbe()
facts = probe.collect()

print(f"主机名: {facts.hostname}")
print(f"系统: {facts.os_name} {facts.os_release}")
print(f"架构: {facts.architecture}")

print("\n已安装工具:")
print(f"  Git:    {'✓' if facts.has_git else '✗'}")
print(f"  Docker: {'✓' if facts.has_docker else '✗'}")
print(f"  Node:   {'✓' if facts.has_node else '✗'}")
print(f"  Python: {'✓' if facts.has_python3 else '✗'}")
```

### Windows 特定用法

```python
import platform
from auto_deployer.local import LocalSession

session = LocalSession()

if platform.system() == "Windows":
    # Windows PowerShell 命令
    result = session.run('Get-Process | Select-Object -First 5')
else:
    # Linux/Mac 命令
    result = session.run('ps aux | head -5')

print(result.stdout)
```

### 设置超时

```python
# 设置 5 分钟超时（用于长时间构建）
result = session.run("npm run build", timeout=300)

if not result.ok:
    if "timed out" in result.stderr:
        print("构建超时")
    else:
        print(f"构建失败: {result.stderr}")
```

### 禁用实时输出

```python
# 禁用实时输出，只获取最终结果
result = session.run("npm install", stream_output=False)
print(f"Exit code: {result.exit_status}")
print(f"Output: {result.stdout}")
```

---

## 与 SSHSession 接口对比

`LocalSession` 和 `SSHSession` 提供相同的接口，便于统一处理：

```python
from auto_deployer.local import LocalSession
from auto_deployer.ssh import SSHSession

def run_deployment(session):
    """通用部署函数，接受 LocalSession 或 SSHSession"""
    result = session.run("git clone ...")
    if result.ok:
        session.run("npm install")
        session.run("npm run build")
    return result.ok

# 本地部署
with LocalSession() as session:
    run_deployment(session)

# 远程部署
with SSHSession(credentials) as session:
    run_deployment(session)
```

---

## 相关文档

- [workflow](workflow.md) - 工作流中使用 LocalSession
- [agent](agent.md) - Agent 使用 LocalSession
- [ssh](ssh.md) - 远程会话（类似接口）

