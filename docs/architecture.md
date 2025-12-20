# Auto-Deployer 架构设计

## 1. 概述

Auto-Deployer 是一个 **LLM 驱动的自动化部署工具**。它通过让大语言模型（LLM）作为自主 Agent，分析项目结构并决定执行什么命令，从而实现全自动化部署。

### 核心设计理念

- **Plan-Execute 架构**：规划和执行分离，LLM先生成完整部署计划，再按步骤执行
- **步骤级控制**：每个步骤独立执行，有明确的边界和迭代预算
- **自我修复能力**：遇到错误时，Agent 会分析日志并尝试修复
- **人机协作**：关键决策点可以询问用户，避免盲目操作
- **经验积累**：从历史部署中学习，提升未来部署成功率

### 与传统部署工具的区别

| 特性 | 传统工具 (Ansible/Shell) | Auto-Deployer |
|------|-------------------------|---------------|
| 部署逻辑 | 预定义脚本 | LLM 实时决策 |
| 错误处理 | 预设条件分支 | 智能分析修复 |
| 项目适配 | 需要编写 Playbook | 自动识别项目类型 |
| 用户交互 | 参数预配置 | 按需询问 |

---

## 2. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户接口层 (Interface Layer)                    │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐                    │
│  │   CLI       │   │  Python API │   │  (Future)   │                    │
│  │  cli.py     │   │  直接调用    │   │  Web UI     │                    │
│  └──────┬──────┘   └──────┬──────┘   └─────────────┘                    │
│         │                 │                                              │
│         └────────┬────────┘                                              │
│                  ▼                                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                          编排层 (Orchestration Layer)                    │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                    DeploymentWorkflow                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│  │  │ 1.分析仓库  │─▶│ 2.建立连接  │─▶│ 3.Agent部署 │                │  │
│  │  │ RepoAnalyzer│  │SSH/Local    │  │DeployAgent  │                │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                           智能层 (Intelligence Layer)                    │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                      DeploymentAgent                               │  │
│  │                                                                    │  │
│  │   ┌──────────┐      ┌──────────┐      ┌──────────┐                │  │
│  │   │ Observe  │ ───▶ │  Think   │ ───▶ │   Act    │                │  │
│  │   │ 收集状态  │      │ LLM决策  │      │ 执行命令  │                │  │
│  │   └──────────┘      └──────────┘      └────┬─────┘                │  │
│  │        ▲                                    │                      │  │
│  │        └────────────────────────────────────┘                      │  │
│  │                      (循环直到完成或失败)                            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ InteractionHdlr │  │ ExperienceRetr  │  │    LLM API      │         │
│  │ 用户交互处理     │  │ 经验检索        │  │ Gemini/OpenAI   │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                          执行层 (Execution Layer)                        │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐      │
│  │        SSHSession           │  │        LocalSession          │      │
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────┐   │      │
│  │  │ run(command)          │  │  │  │ run(command)          │   │      │
│  │  │ - 自动处理 sudo       │  │  │  │ - Windows/Linux 适配  │   │      │
│  │  │ - 实时输出流          │  │  │  │ - 实时输出流          │   │      │
│  │  └───────────────────────┘  │  │  └───────────────────────┘   │      │
│  │        ▼                    │  │        ▼                     │      │
│  │   Remote Linux Server       │  │   Local Machine              │      │
│  └─────────────────────────────┘  └─────────────────────────────┘      │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                         存储层 (Storage Layer)                           │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  agent_logs/    │  │ .auto-deployer/ │  │ config/         │         │
│  │  部署日志(JSON) │  │ knowledge/      │  │ 配置文件        │         │
│  │                 │  │ workspace/      │  │                 │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心组件

### 3.1 部署工作流 (DeploymentWorkflow)

**职责**：编排整个部署流程，协调各组件工作

**位置**：`src/auto_deployer/workflow.py`

**工作流程**：

```
1. 本地分析阶段
   └─ 克隆仓库 → 读取关键文件 → 检测项目类型 → 生成 RepoContext

2. 连接建立阶段
   ├─ SSH 模式：创建 SSHSession，探测远程主机信息
   └─ 本地模式：创建 LocalSession，探测本地主机信息

3. Plan-Execute 部署阶段
   ├─ Phase 1: 创建 DeploymentPlanner → 生成部署计划
   └─ Phase 2: 创建 DeploymentOrchestrator → 按步骤执行
```

**与其他组件的关系**：

- 调用 `RepoAnalyzer` 分析仓库
- 创建 `SSHSession` 或 `LocalSession`
- 使用 `DeploymentPlanner` 生成计划
- 使用 `DeploymentOrchestrator` 执行计划
- 可选注入 `InteractionHandler` 和 `ExperienceRetriever`

---

### 3.2 LLM Agent (DeploymentAgent)

**职责**：作为自主决策核心，通过 LLM 决定部署步骤

**位置**：`src/auto_deployer/llm/agent.py`

**Agent 循环**：

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent 主循环                            │
│                                                             │
│   for iteration in range(max_iterations):                   │
│       │                                                     │
│       ▼                                                     │
│   ┌─────────┐    构建 Prompt（含上下文、历史、经验）          │
│   │ Observe │────────────────────────────────────────────▶  │
│   └─────────┘                                               │
│       │                                                     │
│       ▼                                                     │
│   ┌─────────┐    调用 LLM API，获取 JSON 响应               │
│   │  Think  │────────────────────────────────────────────▶  │
│   └─────────┘                                               │
│       │                                                     │
│       ▼                                                     │
│   ┌─────────┐    解析响应为 AgentAction                     │
│   │  Parse  │────────────────────────────────────────────▶  │
│   └─────────┘                                               │
│       │                                                     │
│       ▼                                                     │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    Act (执行动作)                     │   │
│   │                                                     │   │
│   │  action_type == "execute"  → 执行命令，记录结果      │   │
│   │  action_type == "ask_user" → 询问用户，等待响应      │   │
│   │  action_type == "done"     → 部署成功，退出循环      │   │
│   │  action_type == "failed"   → 部署失败，退出循环      │   │
│   └─────────────────────────────────────────────────────┘   │
│       │                                                     │
│       └─────────────────────────────────────────────────────┘
│                          (继续下一迭代)
└─────────────────────────────────────────────────────────────┘
```

**动作类型**：

| 类型 | 说明 | 示例 |
|------|------|------|
| `execute` | 执行 Shell 命令 | `{"action": "execute", "command": "npm install"}` |
| `ask_user` | 询问用户 | `{"action": "ask_user", "question": "选择端口?", "options": ["3000", "8080"]}` |
| `done` | 部署完成 | `{"action": "done", "message": "应用已在 3000 端口运行"}` |
| `failed` | 部署失败 | `{"action": "failed", "message": "缺少必要的环境变量"}` |

**Prompt 构建策略**：

1. 系统提示词：定义 Agent 角色、可用动作、最佳实践
2. 仓库上下文：项目类型、框架、关键文件内容
3. 主机信息：操作系统、已安装工具
4. 历史经验：从知识库检索的相关经验
5. 命令历史：已执行的命令及其结果
6. 用户交互历史：之前的问答记录

---

### 3.3 仓库分析器 (RepoAnalyzer)

**职责**：克隆仓库并提取部署相关上下文

**位置**：`src/auto_deployer/analyzer/repo_analyzer.py`

**分析流程**：

```
输入: repo_url
        │
        ▼
┌───────────────────┐
│ 1. 克隆仓库       │  git clone --depth 1
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 2. 读取关键文件   │  README, package.json, Dockerfile, etc.
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 3. 生成目录树     │  最大深度 3 层，排除 node_modules 等
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 4. 检测项目类型   │  nodejs, python, go, rust, java, static...
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 5. 检测框架       │  Next.js, FastAPI, Django, Express...
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 6. 提取元数据     │  scripts, dependencies
└─────────┬─────────┘
          │
          ▼
输出: RepoContext
```

**关键文件列表**（按优先级）：

```python
KEY_FILES = [
    # 部署说明
    "README.md", "DEPLOY.md",
    # 包管理
    "package.json", "requirements.txt", "pyproject.toml",
    # 容器化
    "Dockerfile", "docker-compose.yml",
    # 环境配置
    ".env.example",
    # 构建配置
    "Makefile", "vite.config.js", "next.config.js",
    # 进程管理
    "Procfile", "ecosystem.config.js",
    # CI/CD
    ".github/workflows/deploy.yml",
]
```

---

### 3.4 会话管理

#### SSHSession（远程执行）

**职责**：通过 SSH 在远程服务器执行命令

**特性**：

- 支持密码和密钥认证
- 自动处理 sudo 命令（通过 stdin 传递密码）
- 实时输出流（可选）
- 自动加载 nvm 等环境

#### LocalSession（本地执行）

**职责**：在本地机器执行命令

**特性**：

- 支持 Windows (PowerShell) 和 Linux (Bash)
- 基本的命令语法转换
- 实时输出流

**统一接口设计**：

```python
# 两个 Session 类提供相同的接口
class Session(Protocol):
    def connect(self) -> None: ...
    def close(self) -> None: ...
    def run(self, command: str, timeout: int = None) -> CommandResult: ...
```

---

### 3.5 用户交互 (InteractionHandler)

**职责**：处理 Agent 与用户之间的交互

**抽象设计**：

```python
class UserInteractionHandler(ABC):
    @abstractmethod
    def ask(self, request: InteractionRequest) -> InteractionResponse: ...
    
    @abstractmethod
    def notify(self, message: str, level: str) -> None: ...
```

**内置实现**：

| 实现类 | 用途 | 说明 |
|--------|------|------|
| `CLIInteractionHandler` | 命令行交互 | 默认实现，支持选择题、确认、文本输入 |
| `CallbackInteractionHandler` | GUI/Web 集成 | 通过回调函数处理交互 |
| `AutoResponseHandler` | 测试/自动化 | 自动选择默认值或预设响应 |

---

### 3.6 知识库系统 (Knowledge)

**职责**：存储和检索部署经验，提升未来部署成功率

**四个子模块**：

```
┌─────────────────────────────────────────────────────────────┐
│                     Knowledge System                         │
│                                                             │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐  │
│  │  Extractor  │ ───▶ │   Refiner   │ ───▶ │    Store    │  │
│  │ 从日志提取  │      │ LLM 精炼    │      │ ChromaDB    │  │
│  └─────────────┘      └─────────────┘      └──────┬──────┘  │
│                                                    │        │
│                                            ┌───────▼──────┐  │
│                                            │  Retriever   │  │
│                                            │ 语义检索     │  │
│                                            └──────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**数据流**：

1. **提取**：从 `agent_logs/` 中的 JSON 日志提取原始经验
2. **精炼**：使用 LLM 将原始经验转换为结构化的问题-解决方案对
3. **存储**：使用 ChromaDB 向量数据库存储，支持语义搜索
4. **检索**：根据当前部署上下文检索相关经验，注入 Prompt

---

## 4. 数据流图

```
┌──────────┐
│  用户    │
└────┬─────┘
     │ auto-deployer deploy --repo <URL> --host <HOST> ...
     ▼
┌──────────────────────────────────────────────────────────────────┐
│                           CLI (cli.py)                            │
│  解析参数 → 加载配置 → 构建 DeploymentRequest                      │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    DeploymentWorkflow                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Step 1: 分析仓库                                           │  │
│  │                                                            │  │
│  │  repo_url ──▶ RepoAnalyzer ──▶ RepoContext                │  │
│  │              (克隆 + 读取)       (类型/框架/文件)           │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                 │                                │
│                                 ▼                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Step 2: 建立连接                                           │  │
│  │                                                            │  │
│  │  SSH 模式: SSHCredentials ──▶ SSHSession ──▶ RemoteProbe   │  │
│  │  本地模式: LocalSession ──▶ LocalProbe                     │  │
│  │                                    │                       │  │
│  │                                    ▼                       │  │
│  │                              HostFacts                     │  │
│  │                         (OS/内核/已装工具)                  │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                 │                                │
│                                 ▼                                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ Step 3: Agent 部署                                         │  │
│  │                                                            │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │              DeploymentAgent Loop                    │   │  │
│  │  │                                                     │   │  │
│  │  │  Context ──▶ Prompt ──▶ LLM API ──▶ Action          │   │  │
│  │  │     │                                  │             │   │  │
│  │  │     │         ┌────────────────────────┘             │   │  │
│  │  │     │         ▼                                      │   │  │
│  │  │     │    ┌─────────┐                                 │   │  │
│  │  │     │    │ execute │──▶ Session.run() ──▶ Result     │   │  │
│  │  │     │    ├─────────┤                        │        │   │  │
│  │  │     │    │ask_user │──▶ Handler.ask() ──▶ Response   │   │  │
│  │  │     │    ├─────────┤                        │        │   │  │
│  │  │     │    │  done   │──▶ Return Success      │        │   │  │
│  │  │     │    ├─────────┤                        │        │   │  │
│  │  │     │    │ failed  │──▶ Return Failure      │        │   │  │
│  │  │     │    └─────────┘                        │        │   │  │
│  │  │     │                                       │        │   │  │
│  │  │     └───────────────────────────────────────┘        │   │  │
│  │  │                   (更新 history)                      │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   部署结果 + 日志文件   │
                    │  agent_logs/*.json     │
                    └────────────────────────┘
```

---

## 5. 部署模式

### 5.1 SSH 远程部署模式

**适用场景**：
- 部署到远程 Linux 服务器
- 生产环境部署
- 多服务器批量部署（配合脚本）

**流程图**：

```
本地机器                              远程服务器
─────────                            ──────────
    │                                    │
    │  1. 克隆仓库到本地临时目录           │
    │  2. 分析项目结构                    │
    │                                    │
    │ ──── SSH 连接建立 ────────────────▶│
    │                                    │
    │  3. 探测远程主机信息                │◀──┐
    │                                    │   │
    │  4. Agent 循环                     │   │
    │     发送命令 ─────────────────────▶│   │ 命令执行
    │     接收结果 ◀─────────────────────│   │
    │     ...                            │   │
    │                                    │───┘
    │ ──── SSH 连接关闭 ────────────────▶│
    │                                    │
    ▼                                    ▼
  日志保存                           应用运行中
```

### 5.2 本地部署模式

**适用场景**：
- 开发环境快速部署
- 测试 Auto-Deployer 功能
- Windows/Mac 本地开发

**流程图**：

```
本地机器
─────────
    │
    │  1. 克隆仓库到本地临时目录
    │  2. 分析项目结构
    │  3. 探测本地主机信息
    │
    │  4. Agent 循环
    │     ├─ Windows: PowerShell 执行
    │     └─ Linux/Mac: Bash 执行
    │
    ▼
  应用在本地运行
```

**Windows/Linux 差异处理**：

| 操作 | Linux | Windows |
|------|-------|---------|
| 删除目录 | `rm -rf dir` | `Remove-Item -Recurse -Force dir` |
| 创建目录 | `mkdir -p dir` | `New-Item -ItemType Directory -Force dir` |
| 后台运行 | `nohup cmd &` | `Start-Process -NoNewWindow cmd` |
| 环境变量 | `export VAR=val` | `$env:VAR = "val"` |
| 家目录 | `~` | `$env:USERPROFILE` |

---

## 6. 配置体系

### 配置优先级（从高到低）

```
1. CLI 参数        --host, --user, --password, ...
        │
        ▼
2. 环境变量        AUTO_DEPLOYER_SSH_HOST, AUTO_DEPLOYER_GEMINI_API_KEY, ...
        │
        ▼
3. 配置文件        config/default_config.json
        │
        ▼
4. 代码默认值      LLMConfig(), DeploymentConfig(), ...
```

### 配置文件结构

```json
{
  "llm": {
    "provider": "gemini",           // LLM 提供商
    "model": "gemini-2.5-flash",    // 模型名称
    "api_key": null,                // API 密钥（建议用环境变量）
    "endpoint": null,               // 自定义 API 端点
    "temperature": 0.0,             // 温度参数
    "proxy": null                   // HTTP 代理
  },
  "agent": {
    "max_iterations": 40            // 最大迭代次数
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

## 7. 日志与监控

### Agent 日志

**位置**：`agent_logs/deploy_<project>_<timestamp>.json`

**结构**：

```json
{
  "repo_url": "https://github.com/user/project.git",
  "target": "user@server:22",
  "deploy_dir": "~/project",
  "start_time": "2024-12-01T10:00:00",
  "end_time": "2024-12-01T10:05:30",
  "status": "success",              // success | failed | cancelled | max_iterations
  "config": {
    "model": "gemini-2.5-flash",
    "temperature": 0.0,
    "max_iterations": 40
  },
  "context": {
    "project_type": "nodejs",
    "framework": "Next.js"
  },
  "steps": [
    {
      "iteration": 1,
      "timestamp": "...",
      "action": "execute",
      "command": "git clone ...",
      "reasoning": "首先克隆仓库",
      "result": {
        "success": true,
        "exit_code": 0,
        "stdout": "...",
        "stderr": ""
      }
    }
    // ...更多步骤
  ]
}
```

### 查看日志

```bash
# 列出所有日志
auto-deployer logs --list

# 查看最新日志
auto-deployer logs

# 查看摘要
auto-deployer logs --summary
```

---

## 8. 扩展点

> 详细的模块文档请参考 [模块参考](modules/index.md)

### 添加新的 LLM Provider

目前支持 Gemini 和 OpenAI。添加新 Provider 需要：

1. 在 `config.py` 中添加 Provider 配置
2. 在 `agent.py` 中添加 API 调用逻辑
3. 确保响应格式与现有 JSON 格式兼容

### 添加新的 InteractionHandler

实现 `UserInteractionHandler` 抽象类：

```python
class MyCustomHandler(UserInteractionHandler):
    def ask(self, request: InteractionRequest) -> InteractionResponse:
        # 实现自定义交互逻辑
        pass
    
    def notify(self, message: str, level: str) -> None:
        # 实现通知逻辑
        pass
```

然后在创建 `DeploymentWorkflow` 时传入：

```python
workflow = DeploymentWorkflow(
    config=config,
    workspace=workspace,
    interaction_handler=MyCustomHandler()
)
```

### 自定义仓库分析规则

修改 `analyzer/repo_analyzer.py`：

1. 在 `KEY_FILES` 列表中添加新的关键文件
2. 在 `_detect_project_type()` 中添加新的检测规则
3. 在 `_extract_metadata()` 中添加新的元数据提取逻辑

