# SSH 阻塞命令超时机制

## 1. 问题背景

### 1.1 问题描述

在自动化 SSH 部署场景中，某些命令会导致 SSH 会话永久阻塞，无法返回。这类命令通常是：
- 启动交互式 shell 的命令（如 `newgrp`、`su -`）
- 等待用户输入的命令（如 `passwd`、`apt install` 无 `-y`）
- 交互式编辑器（如 `vim`、`nano`）

当 LLM Agent 生成这类命令时，会导致整个部署流程卡死。

### 1.2 影响范围

- **严重程度**：高
- **影响组件**：SSH Session、LLM Agent
- **表现症状**：
  - 部署日志状态停留在 `"running"`
  - 命令执行无限等待，无超时返回
  - 程序需要手动中断

### 1.3 典型案例

```
[2025-12-04 12:42:51] 🔧 Executing: sudo usermod -aG docker ctfy && newgrp docker
   Reason: Add user to docker group and activate it
   
# 命令执行后，输出停止，程序永久卡住
Processing triggers for libc-bin (2.35-0ubuntu3.11) ...
# <- 卡在这里，永远不返回
```

---

## 2. 问题分析

### 2.1 阻塞命令分类

| 类型 | 命令示例 | 阻塞原因 |
|------|----------|----------|
| **启动新 shell** | `newgrp`, `su -`, `bash -i` | 启动交互式 shell，等待用户输入任意命令 |
| **等待确认** | `apt install`(无-y), `rm -i` | 等待 yes/no 确认 |
| **等待密码** | `passwd`, `su`(某些配置) | 等待密码输入 |
| **交互式编辑** | `vim`, `nano`, `less` | 等待编辑操作 |
| **读取输入** | `read VAR` | 等待 stdin 输入 |

### 2.2 为什么会卡住

以 `newgrp docker` 为例：

```
原始 shell (gid=1000)
    │
    └── 执行 newgrp docker
            │
            └── 新启动的子 shell (gid=docker)
                    │
                    └── 等待用户输入... (永远)
```

`newgrp` 不是简单地"切换当前 shell 的组"，而是**启动一个全新的交互式子 shell**。在非交互式 SSH 会话中，没有用户来输入命令，这个新 shell 会永远等待。

### 2.3 原有代码的缺陷

原有的 `SSHSession.run()` 方法中：

```python
# 原代码
while not stdout.channel.exit_status_ready():
    # 读取输出...
    time.sleep(0.1)
# <- 如果命令永不退出，这个循环永远不会结束
```

虽然 `exec_command()` 接受 `timeout` 参数，但该参数只影响 **socket 级别的读写超时**，不是命令执行超时。命令本身如果不退出，循环会永远运行。

---

## 3. 解决方案

### 3.1 方案概述

采用**双层防护**策略：

```
┌─────────────────────────────────────────────────────┐
│  第一层：Prompt 预防                                  │
│  在 LLM 系统提示词中明确禁止阻塞命令                    │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│  第二层：智能超时兜底                                  │
│  基于输出活动检测，无输出时触发超时                      │
└─────────────────────────────────────────────────────┘
```

### 3.2 智能空闲超时机制

**核心思路**：区分"正在执行"和"等待输入"

| 场景 | 输出活动 | 处理方式 |
|------|----------|----------|
| `docker build`（5分钟） | 持续有输出 | 继续等待 |
| `apt update`（2分钟） | 持续有输出 | 继续等待 |
| `newgrp docker` | 无输出 | 60秒后超时 |
| `apt install`(无-y) | 显示提示后无输出 | 60秒后超时 |

**算法**：
```python
last_activity_time = now()

while not command_finished:
    if has_output():
        last_activity_time = now()  # 重置空闲计时器
    
    if (now() - last_activity_time) > IDLE_TIMEOUT:
        return TIMEOUT_ERROR  # 空闲超时
    
    if (now() - start_time) > TOTAL_TIMEOUT:
        return TIMEOUT_ERROR  # 总超时
```

### 3.3 Prompt 预防机制

在 LLM Agent 的系统提示词中添加明确的禁止清单：

```markdown
# ⛔ FORBIDDEN COMMANDS (WILL CAUSE TIMEOUT!)
- `newgrp <group>` - Starts new interactive shell
- `su -` or `su - <user>` - Starts interactive shell
- `passwd` - Requires interactive password input
- `vim`, `nano`, `vi` - Interactive editors
- `apt install` without `-y` - Waits for confirmation
```

---

## 4. 实现细节

### 4.1 SSH Session 修改

**文件**：`src/auto_deployer/ssh/session.py`

**修改内容**：

1. **新增参数**：
   ```python
   def run(
       self,
       command: str,
       *,
       timeout: Optional[int] = None,      # 总超时（默认 600 秒）
       idle_timeout: int = 60,              # 空闲超时（默认 60 秒）
       stream_output: bool = True,
   ) -> SSHCommandResult:
   ```

2. **超时检测逻辑**：
   ```python
   start_time = time.time()
   last_activity_time = time.time()
   
   while not stdout.channel.exit_status_ready():
       has_activity = False
       
       # 读取输出
       if stdout.channel.recv_ready():
           chunk = stdout.channel.recv(1024)
           has_activity = True
       
       # 有输出时重置空闲计时器
       if has_activity:
           last_activity_time = time.time()
       
       # 检查空闲超时
       if (time.time() - last_activity_time) > idle_timeout:
           stdout.channel.close()
           return SSHCommandResult(
               command=command,
               stdout=collected_output,
               stderr="IDLE_TIMEOUT: No output for 60 seconds...",
               exit_status=-1,
           )
       
       # 检查总超时
       if (time.time() - start_time) > timeout:
           stdout.channel.close()
           return SSHCommandResult(
               command=command,
               stdout=collected_output,
               stderr="TOTAL_TIMEOUT: Command exceeded 600 seconds...",
               exit_status=-2,
           )
   ```

### 4.2 Agent Prompt 修改

**文件**：`src/auto_deployer/llm/agent.py`

**修改位置**：`_build_prompt()` 方法中的系统提示词

**添加内容**：
```python
# ⛔ FORBIDDEN COMMANDS (WILL CAUSE TIMEOUT!)
**These commands start interactive shells or wait for input - NEVER use them:**
- `newgrp <group>` - Starts new interactive shell, will timeout after 60s
- `su -` or `su - <user>` (without -c) - Starts interactive shell
- `passwd` - Requires interactive password input
- `vim`, `nano`, `vi`, `less`, `more` - Interactive editors/pagers
- `apt install` without `-y` - Waits for confirmation
- `read` command - Waits for stdin input

**Use these alternatives instead:**
| ❌ Forbidden | ✅ Alternative |
|--------------|----------------|
| `newgrp docker` | `sudo docker ...` or `sg docker -c "docker ..."` |
| `su - user` | `sudo -u user command` |
| `apt install pkg` | `apt-get install -y pkg` |
```

### 4.3 参数配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `timeout` | 600 秒 | 命令总执行时间上限 |
| `idle_timeout` | 60 秒 | 无输出时间上限 |

**调整建议**：
- 对于已知的长时间命令（如大型编译），可以增加 `timeout`
- 对于快速命令，可以减少 `idle_timeout` 以更快检测阻塞

---

## 5. 使用指南

### 5.1 超时参数说明

```python
# 使用默认超时
result = session.run("apt update")

# 自定义超时
result = session.run(
    "make -j4",
    timeout=1800,      # 30 分钟总超时
    idle_timeout=120,  # 2 分钟空闲超时
)
```

### 5.2 错误信息解读

| stderr 内容 | 含义 | 可能原因 |
|-------------|------|----------|
| `IDLE_TIMEOUT: No output for 60 seconds...` | 空闲超时 | 命令等待输入，或真的长时间无输出 |
| `TOTAL_TIMEOUT: Command exceeded 600 seconds...` | 总超时 | 命令执行时间过长 |
| `TIMEOUT: Command did not complete...` | 非流式模式超时 | 同上 |

| exit_status | 含义 |
|-------------|------|
| `-1` | 空闲超时或非流式超时 |
| `-2` | 总超时 |

### 5.3 常见问题处理

**Q: 正常的长时间命令被误杀怎么办？**

A: 增加 `idle_timeout` 参数，或确保命令有持续输出（如添加 verbose 选项）

**Q: LLM 仍然生成了阻塞命令怎么办？**

A: 超时机制会在 60 秒后返回错误，LLM 可以从错误信息中学习并调整策略

**Q: 超时后 SSH 连接还能用吗？**

A: 可以。超时只关闭当前命令的 channel，不影响 SSH 连接本身

---

## 6. 附录

### 6.1 阻塞命令清单

| 命令 | 类型 | 风险等级 |
|------|------|----------|
| `newgrp <group>` | 启动新 shell | 🔴 高 |
| `su -` | 启动新 shell | 🔴 高 |
| `su - <user>` | 启动新 shell | 🔴 高 |
| `bash -i` | 启动新 shell | 🔴 高 |
| `passwd` | 等待密码 | 🔴 高 |
| `vim`, `nano`, `vi` | 交互式编辑 | 🔴 高 |
| `less`, `more` | 交互式分页 | 🟡 中 |
| `apt install`(无-y) | 等待确认 | 🟡 中 |
| `apt-get install`(无-y) | 等待确认 | 🟡 中 |
| `read VAR` | 等待输入 | 🟡 中 |
| `systemctl edit` | 启动编辑器 | 🟡 中 |

### 6.2 替代方案速查表

| ❌ 阻塞命令 | ✅ 替代方案 |
|-------------|-------------|
| `newgrp docker` | `sudo docker ...` |
| `newgrp docker && cmd` | `sg docker -c "cmd"` |
| `su - user` | `sudo -u user command` |
| `su - user -c "cmd"` | `sudo -u user cmd` |
| `apt install pkg` | `apt-get install -y pkg` |
| `apt-get install pkg` | `apt-get install -y pkg` |
| `systemctl edit svc` | `sudo bash -c 'cat > /etc/systemd/...'` |
| `passwd user` | `echo "user:password" \| sudo chpasswd` |
| `read VAR` | 使用命令参数或环境变量 |
| `vim file` | `echo "content" > file` 或 `cat > file <<EOF` |

---

## 更新历史

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2025-12-04 | 1.0 | 初始版本，实现智能空闲超时机制 |

