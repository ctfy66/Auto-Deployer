# 部署规划模块 (Deployment Planning)

Agent 规划部署步骤功能的完整技术文档。

**模块路径**：
- `auto_deployer.llm.agent` - DeploymentPlan, DeploymentStep, DeploymentPlanner
- `auto_deployer.orchestrator` - DeploymentOrchestrator, StepExecutor

---

## 概述

部署规划功能采用**两阶段设计**，将传统的"边执行边思考"模式升级为"先规划后执行"，显著提高部署的可预测性和成功率。

### 架构优势

```
传统模式 (Reactive):
┌─────────────────────────────────────────────┐
│  LLM 循环：观察 → 思考 → 执行 → 观察 → ...   │
│  问题：容易迷路、重复尝试、难以预测结果      │
└─────────────────────────────────────────────┘

新模式 (Plan-Execute):
┌────────────────────┐    ┌─────────────────────────┐
│  Phase 1: 规划      │ ─▶ │  Phase 2: 执行          │
│  LLM 生成完整计划   │    │  按步骤执行，每步LLM决策│
│  - 识别项目类型     │    │  - Step 1 → 循环        │
│  - 选择部署策略     │    │  - Step 2 → 循环        │
│  - 拆解成步骤       │    │  - ...                  │
│  - 识别风险         │    │                         │
└────────────────────┘    └─────────────────────────┘
```

---

## 核心数据结构

### DeploymentStep

单个部署步骤的定义。

```python
@dataclass
class DeploymentStep:
    id: int                                   # 步骤ID（从1开始）
    name: str                                 # 步骤名称，如 "Install Node.js"
    description: str                          # 详细描述
    category: str                             # 类别，见下表
    estimated_commands: List[str]             # 预计执行的命令（仅供参考）
    success_criteria: str                     # 成功标准，如 "docker ps shows container running"
    depends_on: List[int] = []                # 依赖的步骤ID列表
```

#### 步骤类别 (Category)

| 类别 | 说明 | 示例 |
|------|------|------|
| `prerequisite` | 安装必要软件 | 安装 Docker、Node.js、Python |
| `setup` | 配置环境 | 克隆仓库、复制配置文件、设置环境变量 |
| `build` | 构建应用 | npm build、docker build |
| `deploy` | 启动服务 | docker-compose up、启动 nginx |
| `verify` | 验证部署 | curl 检查 HTTP 200、检查进程状态 |

#### 示例

```python
DeploymentStep(
    id=3,
    name="Build Docker image",
    description="Build the application Docker image from Dockerfile",
    category="build",
    estimated_commands=[
        "cd ~/myapp",
        "docker build -t myapp:latest .",
    ],
    success_criteria="docker images shows myapp:latest",
    depends_on=[1, 2],  # 依赖步骤1和2
)
```

---

### DeploymentPlan

完整的部署方案。

```python
@dataclass
class DeploymentPlan:
    strategy: str                             # 部署策略，见下表
    components: List[str]                     # 需要的组件，如 ["docker", "nginx"]
    steps: List[DeploymentStep]               # 步骤列表（按执行顺序）
    risks: List[str]                          # 已识别的风险
    notes: List[str]                          # 注意事项
    estimated_time: str                       # 预计时间，如 "5-10 minutes"
    created_at: str                           # 创建时间 (ISO 格式)
```

#### 部署策略 (Strategy)

| 策略 | 触发条件 | 说明 |
|------|----------|------|
| `docker-compose` | 存在 `docker-compose.yml` | 最优选择，自动处理多服务项目 |
| `docker` | 仅存在 `Dockerfile` | 单容器应用 |
| `traditional` | 无 Docker 文件 | 传统部署（npm/pip + PM2/systemd） |
| `static` | 纯静态文件 | 使用 nginx 或 python http.server |

#### 示例

```python
DeploymentPlan(
    strategy="docker-compose",
    components=["docker", "docker-compose"],
    steps=[
        DeploymentStep(id=1, name="Install Docker", ...),
        DeploymentStep(id=2, name="Clone repository", ...),
        DeploymentStep(id=3, name="Start services", ...),
        DeploymentStep(id=4, name="Verify deployment", ...),
    ],
    risks=[
        "Missing .env file - may need user input",
        "Port 80 might be occupied",
    ],
    notes=[
        "Application exposes port 3000",
    ],
    estimated_time="3-5 minutes",
)
```

#### 转换为字典

```python
plan_dict = plan.to_dict()
# 用于日志记录和 JSON 序列化
```

---

## 规划器 (DeploymentPlanner)

独立的部署计划生成器，通过 LLM 分析仓库并生成结构化计划。

### 类定义

```python
class DeploymentPlanner:
    def __init__(
        self,
        config: LLMConfig,
        planning_timeout: int = 60,
    ) -> None: ...
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `LLMConfig` | LLM 配置（必须包含 `api_key`） |
| `planning_timeout` | `int` | 规划超时时间（秒），默认 60 |

### 核心方法

#### create_plan

生成部署计划。

```python
def create_plan(
    self,
    repo_url: str,
    deploy_dir: str,
    host_info: dict,
    repo_analysis: Optional[str] = None,
    project_type: Optional[str] = None,
    framework: Optional[str] = None,
    is_local: bool = False,
) -> Optional[DeploymentPlan]
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `repo_url` | `str` | 仓库 URL |
| `deploy_dir` | `str` | 部署目录 |
| `host_info` | `dict` | 主机信息（OS、内核版本等） |
| `repo_analysis` | `Optional[str]` | 仓库分析结果（prompt 格式） |
| `project_type` | `Optional[str]` | 项目类型（nodejs、python 等） |
| `framework` | `Optional[str]` | 框架（Next.js、Django 等） |
| `is_local` | `bool` | 是否本地部署 |

**返回**：`DeploymentPlan` 或 `None`（生成失败时）

#### display_plan (静态方法)

在控制台展示计划。

```python
@staticmethod
def display_plan(plan: DeploymentPlan) -> None
```

**输出示例**：

```
============================================================
📋 DEPLOYMENT PLAN
============================================================

Strategy: DOCKER-COMPOSE
Components: docker, docker-compose
Estimated Time: 5-10 minutes

Steps:
  1. 🔧 [PREREQUISITE] Install Docker
      Ensure Docker is installed and running
      ✓ Success: docker --version returns successfully
  2. 📦 [SETUP] Clone repository
      Clone the project to deployment directory
  3. 🚀 [DEPLOY] Start services with docker-compose
      Launch all services defined in docker-compose.yml
  4. ✅ [VERIFY] Verify application is running
      Check HTTP 200 response from application

⚠️  Identified Risks:
  - Missing .env file - may need user input
  - Port 80 might be occupied

📝 Notes:
  - Application exposes port 3000

============================================================
```

---

## 规划阶段 Prompt 构建

规划器通过精心设计的 Prompt 让 LLM 生成结构化计划。

### Prompt 模板

```python
def _build_planning_prompt(self, context: dict) -> str
```

**Prompt 包含**：

1. **角色定义**：DevOps 部署规划专家
2. **输入信息**：
   - 仓库 URL
   - 部署目录
   - 目标主机（本地/远程）
   - 项目类型和框架
3. **仓库分析结果**：
   - 目录结构
   - 关键文件内容（package.json、Dockerfile 等）
   - 可用脚本
4. **任务说明**：
   - 选择最佳部署策略
   - 识别必需组件
   - 拆解为原子步骤
   - 识别潜在风险
5. **输出格式**：严格的 JSON Schema

### 规划规则

LLM 遵循以下规则生成计划：

```
1. 策略选择（按优先级）：
   - 有 docker-compose.yml → 使用 "docker-compose"
   - 仅有 Dockerfile → 使用 "docker"
   - 无 Docker 文件 → 使用 "traditional" 或 "static"

2. 步骤要求：
   - 每个步骤必须是原子的（单一职责）
   - 每个步骤必须有明确的成功标准
   - 必须包含验证步骤（verify）
   - 按依赖关系排序

3. 成功标准示例：
   ✅ GOOD: "curl http://localhost:3000 返回 HTTP 200"
   ✅ GOOD: "docker ps 显示容器 myapp 正在运行"
   ❌ BAD: "应用正常运行"（不可验证）

4. 风险识别：
   - 从仓库分析中识别（如缺少 .env.example）
   - 常见问题（如端口冲突、权限问题）
```

### 响应格式

LLM 返回纯 JSON（无 markdown 代码块）：

```json
{
  "strategy": "docker-compose",
  "components": ["docker", "docker-compose"],
  "steps": [
    {
      "id": 1,
      "name": "Install Docker",
      "description": "Install Docker Engine and Docker Compose",
      "category": "prerequisite",
      "estimated_commands": [
        "curl -fsSL https://get.docker.com -o get-docker.sh",
        "sudo sh get-docker.sh",
        "sudo usermod -aG docker $USER"
      ],
      "success_criteria": "docker --version && docker-compose --version",
      "depends_on": []
    },
    {
      "id": 2,
      "name": "Clone repository",
      "description": "Clone project to ~/myapp",
      "category": "setup",
      "estimated_commands": [
        "git clone https://github.com/user/myapp.git ~/myapp"
      ],
      "success_criteria": "Directory ~/myapp exists and contains docker-compose.yml",
      "depends_on": []
    }
  ],
  "risks": [
    "Missing .env file - may need user to provide environment variables",
    "Port 80 might be occupied by existing service"
  ],
  "notes": [
    "Application will be accessible on http://host:3000"
  ],
  "estimated_time": "5-10 minutes"
}
```

---

## 执行阶段 (Orchestrator)

部署编排器按顺序执行计划中的每个步骤。

### DeploymentOrchestrator

```python
class DeploymentOrchestrator:
    def __init__(
        self,
        llm_config: LLMConfig,
        session: Union[SSHSession, LocalSession],
        interaction_handler: UserInteractionHandler,
        log_dir: Optional[str] = None,
        max_iterations_per_step: int = 10,
        is_windows: bool = False,
    ): ...
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `llm_config` | `LLMConfig` | LLM 配置 |
| `session` | `SSHSession` 或 `LocalSession` | 命令执行会话 |
| `interaction_handler` | `UserInteractionHandler` | 用户交互处理器 |
| `log_dir` | `Optional[str]` | 日志目录 |
| `max_iterations_per_step` | `int` | 每个步骤的最大迭代次数，默认 10 |
| `is_windows` | `bool` | 是否 Windows 系统 |

### 核心方法：run

执行部署计划。

```python
def run(
    self,
    plan: DeploymentPlan,
    deploy_ctx: DeployContext,
) -> bool
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `plan` | `DeploymentPlan` | 部署计划 |
| `deploy_ctx` | `DeployContext` | 全局部署上下文 |

**返回**：`True` = 部署成功，`False` = 部署失败

---

### 执行流程

```
┌─────────────────────────────────────────────────────────┐
│  DeploymentOrchestrator.run(plan, deploy_ctx)          │
│                                                         │
│  for each step in plan.steps:                          │
│      │                                                  │
│      ▼                                                  │
│  ┌────────────────────────────────────────────────┐    │
│  │ 1. 检查依赖                                     │    │
│  │    - 检查 depends_on 中的步骤是否已成功        │    │
│  │    - 如果依赖未满足 → 跳过步骤                 │    │
│  └────────────────────────────────────────────────┘    │
│      │                                                  │
│      ▼                                                  │
│  ┌────────────────────────────────────────────────┐    │
│  │ 2. 创建 StepContext                            │    │
│  │    - step_id, step_name                        │    │
│  │    - goal, success_criteria                    │    │
│  │    - category                                  │    │
│  └────────────────────────────────────────────────┘    │
│      │                                                  │
│      ▼                                                  │
│  ┌────────────────────────────────────────────────┐    │
│  │ 3. StepExecutor.execute(step_ctx, deploy_ctx)  │    │
│  │                                                │    │
│  │    ┌────────────────────────────────────┐     │    │
│  │    │ 步骤内 LLM 决策循环                │     │    │
│  │    │ (最多 max_iterations_per_step 次)  │     │    │
│  │    │                                    │     │    │
│  │    │ for iteration in 1..max:           │     │    │
│  │    │     action = LLM.decide()          │     │    │
│  │    │                                    │     │    │
│  │    │     if action == "execute":        │     │    │
│  │    │         run_command()              │     │    │
│  │    │         continue loop              │     │    │
│  │    │                                    │     │    │
│  │    │     if action == "step_done":      │     │    │
│  │    │         return SUCCESS             │     │    │
│  │    │                                    │     │    │
│  │    │     if action == "step_failed":    │     │    │
│  │    │         return FAILED              │     │    │
│  │    │                                    │     │    │
│  │    │     if action == "ask_user":       │     │    │
│  │    │         response = ask_user()      │     │    │
│  │    │         continue loop              │     │    │
│  │    └────────────────────────────────────┘     │    │
│  └────────────────────────────────────────────────┘    │
│      │                                                  │
│      ▼                                                  │
│  ┌────────────────────────────────────────────────┐    │
│  │ 4. 处理步骤结果                                 │    │
│  │                                                │    │
│  │    if result == SUCCESS:                       │    │
│  │        记录输出到 shared_data                  │    │
│  │        继续下一步                              │    │
│  │                                                │    │
│  │    if result == FAILED:                        │    │
│  │        询问用户: Retry / Skip / Abort          │    │
│  │        - Retry → 重新执行此步骤                │    │
│  │        - Skip → 标记为跳过，继续下一步         │    │
│  │        - Abort → 终止部署                     │    │
│  └────────────────────────────────────────────────┘    │
│                                                         │
│  所有步骤完成 → return True                             │
│  任何步骤中止 → return False                            │
└─────────────────────────────────────────────────────────┘
```

---

## 步骤执行器 (StepExecutor)

在单个步骤边界内进行 LLM 决策循环。

### 类定义

```python
class StepExecutor:
    def __init__(
        self,
        llm_config: LLMConfig,
        session: Union[SSHSession, LocalSession],
        interaction_handler: UserInteractionHandler,
        max_iterations_per_step: int = 10,
        is_windows: bool = False,
    ): ...
```

### 核心方法：execute

执行单个步骤。

```python
def execute(
    self,
    step_ctx: StepContext,
    deploy_ctx: DeployContext,
) -> StepResult
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `step_ctx` | `StepContext` | 步骤上下文（目标、成功标准） |
| `deploy_ctx` | `DeployContext` | 全局部署上下文（仓库信息等） |

**返回**：`StepResult` - 包含 `success`、`status`、`outputs`、`error`

---

### 步骤内动作类型 (ActionType)

| 动作 | 说明 | LLM 返回格式 |
|------|------|--------------|
| `EXECUTE` | 执行命令 | `{"action": "execute", "command": "...", "reasoning": "..."}` |
| `STEP_DONE` | 步骤完成 | `{"action": "step_done", "message": "...", "outputs": {...}}` |
| `STEP_FAILED` | 步骤失败 | `{"action": "step_failed", "message": "..."}` |
| `ASK_USER` | 询问用户 | `{"action": "ask_user", "question": "...", "options": [...]}` |

---

### 步骤执行 Prompt

StepExecutor 使用专门的 Prompt 模板（见 `orchestrator/prompts.py`）。

**Prompt 特点**：

1. **聚焦单个步骤**：
   ```
   Current Step:
   - ID: 3
   - Name: "Build Docker image"
   - Goal: "Build the application Docker image from Dockerfile"
   - Success Criteria: "docker images shows myapp:latest"
   ```

2. **提供上下文**：
   ```
   - Repository: https://github.com/user/myapp.git
   - Deploy Directory: ~/myapp
   - Host Info: {...}
   ```

3. **显示历史**：
   ```
   Commands Executed in This Step:
   1. [SUCCESS] cd ~/myapp
      stdout: (current directory)
   2. [FAILED] docker build -t myapp .
      stderr: Cannot connect to Docker daemon
   ```

4. **可用动作**：
   ```
   1. Execute command:
      {"action": "execute", "command": "...", "reasoning": "..."}
   
   2. Step done:
      {"action": "step_done", "message": "...", "outputs": {...}}
   
   3. Step failed:
      {"action": "step_failed", "message": "..."}
   
   4. Ask user:
      {"action": "ask_user", "question": "...", "options": [...]}
   ```

5. **关键规则**：
   ```
   1. 只专注当前步骤的目标（不考虑其他步骤）
   2. 使用 success_criteria 判断步骤是否完成
   3. 命令失败时分析错误并尝试替代方案
   4. 最多 max_iterations 次迭代
   5. 一旦满足成功标准立即声明 step_done
   ```

---

## 数据模型

### DeployContext

全局部署上下文，在所有步骤间共享。

```python
@dataclass
class DeployContext:
    repo_url: str
    deploy_dir: str
    host_info: Dict[str, Any]              # 主机信息
    repo_analysis: Optional[str] = None    # 仓库分析 prompt
    project_type: Optional[str] = None     # 如 "nodejs"
    framework: Optional[str] = None        # 如 "Next.js"
    
    shared_data: Dict[str, Any] = field(default_factory=dict)  # 步骤间共享数据
    step_results: Dict[int, StepResult] = field(default_factory=dict)  # 所有步骤结果
```

**用途**：
- `shared_data`：步骤可以将输出写入这里供后续步骤使用
- `step_results`：记录每个步骤的执行结果，用于依赖检查

---

### StepContext

单个步骤的执行上下文。

```python
@dataclass
class StepContext:
    step_id: int
    step_name: str
    goal: str                                # 步骤目标
    success_criteria: str                    # 成功标准
    category: str                            # 步骤类别
    
    # 执行状态
    status: StepStatus = StepStatus.PENDING
    iteration: int = 0                       # 当前迭代次数
    max_iterations: int = 10
    
    # 执行记录
    commands: List[CommandRecord] = field(default_factory=list)
    user_interactions: List[Dict] = field(default_factory=list)
    
    # 输出（传递给 shared_data）
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    # 错误信息
    error: Optional[str] = None
```

---

### StepResult

步骤执行结果。

```python
@dataclass
class StepResult:
    success: bool
    status: StepStatus        # SUCCESS, FAILED, SKIPPED
    outputs: Dict[str, Any]   # 输出数据
    error: Optional[str]      # 错误信息
    commands_count: int       # 执行的命令数
```

**工厂方法**：

```python
# 成功
result = StepResult.succeeded(outputs={"port": 3000})

# 失败
result = StepResult.failed(error="Docker daemon not running")

# 跳过
result = StepResult.skipped(reason="Dependency not met")
```

---

## 完整使用示例

### 示例 1：使用 DeploymentAgent（集成模式）

`DeploymentAgent` 内置了规划功能，可以一键完成规划和执行。

```python
from auto_deployer.llm.agent import DeploymentAgent
from auto_deployer.config import LLMConfig
from auto_deployer.ssh import SSHSession, SSHCredentials
from auto_deployer.workflow import DeploymentRequest
from auto_deployer.analyzer import RepoAnalyzer

# 1. 配置 LLM
llm_config = LLMConfig(
    provider="gemini",
    model="gemini-2.5-flash",
    api_key="your-api-key",
    temperature=0.0,
)

# 2. 创建 Agent（启用规划）
agent = DeploymentAgent(
    config=llm_config,
    max_iterations=30,
    log_dir="./logs",
    enable_planning=True,           # ✅ 启用规划阶段
    require_plan_approval=True,     # ✅ 显示计划并请求用户确认
    planning_timeout=60,
)

# 3. 分析仓库（可选但推荐）
analyzer = RepoAnalyzer()
repo_context = analyzer.analyze("https://github.com/user/myapp.git")

# 4. 创建 SSH 会话
creds = SSHCredentials(
    host="192.168.1.100",
    username="deploy",
    password="secret",
)
session = SSHSession(creds)
session.connect()

# 5. 创建部署请求
request = DeploymentRequest(
    repo_url="https://github.com/user/myapp.git",
    host="192.168.1.100",
    username="deploy",
    auth_method="password",
    password="secret",
    deploy_dir="~/myapp",
)

# 6. 执行部署（自动规划 + 执行）
success = agent.deploy(
    request=request,
    host_facts=None,
    ssh_session=session,
    repo_context=repo_context,
)

if success:
    print(f"✅ 部署成功")
    print(f"📄 日志: {agent.current_log_file}")
else:
    print(f"❌ 部署失败")
```

**执行过程**：

```
============================================================
🚀 Auto-Deployer Agent Starting
============================================================
📋 Configuration:
   LLM Model:      gemini-2.5-flash
   Max Iterations: 30
   Temperature:    0.00

🎯 Deployment Target:
   Repository:     https://github.com/user/myapp.git
   Server:         deploy@192.168.1.100:22
   Deploy Dir:     ~/myapp

📦 Repository Analysis:
   Project Type:   nodejs
   Framework:      Next.js
============================================================

📋 Phase 1: Creating deployment plan...

============================================================
📋 DEPLOYMENT PLAN
============================================================

Strategy: DOCKER-COMPOSE
Components: docker, docker-compose
Estimated Time: 5-10 minutes

Steps:
  1. 🔧 [PREREQUISITE] Install Docker
      Ensure Docker is installed and running
  2. 📦 [SETUP] Clone repository
      Clone the project to ~/myapp
  3. 🏗️ [BUILD] Build Docker image
      Build application image from Dockerfile
  4. 🚀 [DEPLOY] Start services
      Launch services with docker-compose up
  5. ✅ [VERIFY] Verify deployment
      Check application responds with HTTP 200

⚠️  Identified Risks:
  - Missing .env file - may need user input

============================================================

? Do you want to proceed with this deployment plan?
  > Yes, proceed with this plan
    No, cancel deployment

🚀 Phase 2: Executing deployment plan...

📍 Step 1/5: Install Docker (Iteration 1)
   🔧 [1] curl -fsSL https://get.docker.com -o get-docker.sh
      ✓ Exit code: 0
   🔧 [2] sudo sh get-docker.sh
      ✓ Exit code: 0
   ✅ Step completed: Docker installed successfully

📍 Step 2/5: Clone repository (Iteration 1)
   🔧 [1] git clone https://github.com/user/myapp.git ~/myapp
      ✓ Exit code: 0
   ✅ Step completed: Repository cloned

... (继续其他步骤)

============================================================
✅ Agent completed: Application is running on port 3000
📄 Log saved to: ./logs/deploy_myapp_20241205_120000.json
============================================================
```

---

### 示例 2：使用 Planner + Orchestrator（分离模式）

手动分离规划和执行阶段，适合需要自定义逻辑的场景。

```python
from auto_deployer.llm.agent import DeploymentPlanner
from auto_deployer.orchestrator import DeploymentOrchestrator
from auto_deployer.orchestrator.models import DeployContext
from auto_deployer.config import LLMConfig
from auto_deployer.ssh import SSHSession, SSHCredentials
from auto_deployer.interaction import CLIInteractionHandler

# 1. 配置
llm_config = LLMConfig(
    provider="gemini",
    model="gemini-2.5-flash",
    api_key="your-api-key",
)

# 2. 创建规划器
planner = DeploymentPlanner(
    config=llm_config,
    planning_timeout=60,
)

# 3. 生成计划
plan = planner.create_plan(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/myapp",
    host_info={"os_release": "Ubuntu 22.04", "kernel": "5.15.0"},
    repo_analysis=repo_context.to_prompt_context(),  # 从 RepoAnalyzer 获取
    project_type="nodejs",
    framework="Next.js",
    is_local=False,
)

if not plan:
    print("❌ Failed to create deployment plan")
    exit(1)

# 4. 显示计划
DeploymentPlanner.display_plan(plan)

# 5. 用户确认
confirm = input("Proceed with this plan? (y/n): ")
if confirm.lower() != 'y':
    print("Deployment cancelled")
    exit(0)

# 6. 创建部署上下文
deploy_ctx = DeployContext(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/myapp",
    host_info={"os_release": "Ubuntu 22.04", "kernel": "5.15.0"},
    repo_analysis=repo_context.to_prompt_context(),
    project_type="nodejs",
    framework="Next.js",
)

# 7. 创建编排器
session = SSHSession(SSHCredentials(...))
session.connect()

orchestrator = DeploymentOrchestrator(
    llm_config=llm_config,
    session=session,
    interaction_handler=CLIInteractionHandler(),
    log_dir="./logs",
    max_iterations_per_step=10,
)

# 8. 执行计划
success = orchestrator.run(plan, deploy_ctx)

if success:
    print(f"✅ Deployment successful")
    print(f"📄 Log: {orchestrator.current_log_file}")
else:
    print(f"❌ Deployment failed")
```

---

### 示例 3：本地部署

```python
from auto_deployer.llm.agent import DeploymentAgent
from auto_deployer.local import LocalSession
from auto_deployer.workflow import LocalDeploymentRequest

# 创建 Agent
agent = DeploymentAgent(
    config=llm_config,
    enable_planning=True,
)

# 创建本地会话
local_session = LocalSession()

# 本地部署请求
request = LocalDeploymentRequest(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/myapp",
)

# 执行
success = agent.deploy_local(
    request=request,
    host_facts=None,
    local_session=local_session,
    repo_context=repo_context,
)
```

---

## 日志格式

### Orchestrator 模式日志

```json
{
  "version": "2.0",
  "mode": "orchestrator",
  "repo_url": "https://github.com/user/myapp.git",
  "deploy_dir": "~/myapp",
  "project_type": "nodejs",
  "framework": "Next.js",
  "start_time": "2024-12-05T12:00:00",
  "end_time": "2024-12-05T12:08:30",
  "status": "success",
  "config": {
    "model": "gemini-2.5-flash",
    "temperature": 0.0,
    "max_iterations_per_step": 10
  },
  "plan": {
    "strategy": "docker-compose",
    "components": ["docker", "docker-compose"],
    "steps": [
      {
        "id": 1,
        "name": "Install Docker",
        "description": "...",
        "category": "prerequisite",
        "estimated_commands": ["..."],
        "success_criteria": "...",
        "depends_on": []
      }
    ],
    "risks": ["..."],
    "notes": ["..."],
    "estimated_time": "5-10 minutes"
  },
  "steps": [
    {
      "step_id": 1,
      "step_name": "Install Docker",
      "category": "prerequisite",
      "status": "success",
      "iterations": 3,
      "commands": [
        {
          "command": "curl -fsSL https://get.docker.com -o get-docker.sh",
          "success": true,
          "exit_code": 0,
          "stdout": "...",
          "stderr": "",
          "timestamp": "2024-12-05T12:01:00"
        }
      ],
      "user_interactions": [],
      "outputs": {},
      "error": null,
      "timestamp": "2024-12-05T12:02:30"
    }
  ],
  "summary": {
    "total_steps": 5,
    "successful_steps": 5,
    "total_commands": 12,
    "duration_seconds": 510
  }
}
```

---

## 配置选项

### DeploymentAgent 配置

```python
agent = DeploymentAgent(
    config=llm_config,
    max_iterations=30,              # 总最大迭代（不使用规划模式时）
    log_dir="./agent_logs",
    interaction_handler=None,       # 默认使用 CLI
    experience_retriever=None,      # 可选：经验检索器
    
    # 规划相关配置
    enable_planning=True,           # ✅ 是否启用规划阶段
    require_plan_approval=False,    # 是否需要用户批准计划
    planning_timeout=60,            # 规划阶段超时（秒）
)
```

### Orchestrator 配置

```python
orchestrator = DeploymentOrchestrator(
    llm_config=llm_config,
    session=session,
    interaction_handler=handler,
    log_dir="./logs",
    max_iterations_per_step=10,     # ✅ 每个步骤的最大迭代次数
    is_windows=False,               # 是否 Windows 系统
)
```

---

## 最佳实践

### 1. 启用规划模式

```python
# ✅ 推荐：启用规划
agent = DeploymentAgent(
    config=llm_config,
    enable_planning=True,
)

# ❌ 不推荐：禁用规划（回退到传统响应式模式）
agent = DeploymentAgent(
    config=llm_config,
    enable_planning=False,
)
```

**原因**：规划模式显著提高成功率和可预测性。

---

### 2. 提供仓库分析结果

```python
from auto_deployer.analyzer import RepoAnalyzer

# ✅ 推荐：预先分析仓库
analyzer = RepoAnalyzer()
repo_context = analyzer.analyze(repo_url)

agent.deploy(..., repo_context=repo_context)

# ❌ 不推荐：不提供分析结果
agent.deploy(..., repo_context=None)
```

**原因**：仓库分析提供关键信息（项目类型、框架、关键文件），让 LLM 生成更准确的计划。

---

### 3. 设置合理的迭代次数

```python
# 推荐配置
orchestrator = DeploymentOrchestrator(
    llm_config=llm_config,
    session=session,
    interaction_handler=handler,
    max_iterations_per_step=10,  # 每个步骤 10 次迭代通常够用
)
```

**经验值**：
- 简单步骤（如安装软件）：2-3 次迭代
- 中等步骤（如构建应用）：3-5 次迭代
- 复杂步骤（如排查错误）：5-10 次迭代

---

### 4. 编写清晰的成功标准

```python
# ✅ GOOD: 可验证的成功标准
DeploymentStep(
    name="Start application",
    success_criteria="curl http://localhost:3000 returns HTTP 200",
)

# ❌ BAD: 模糊的成功标准
DeploymentStep(
    name="Start application",
    success_criteria="Application is running",
)
```

**原因**：明确的成功标准让 LLM 知道何时完成步骤。

---

### 5. 合理划分步骤粒度

```python
# ✅ GOOD: 原子步骤，单一职责
steps = [
    DeploymentStep(id=1, name="Install Docker", ...),
    DeploymentStep(id=2, name="Clone repository", ...),
    DeploymentStep(id=3, name="Create .env file", ...),
    DeploymentStep(id=4, name="Start containers", ...),
]

# ❌ BAD: 步骤过大，包含多个职责
steps = [
    DeploymentStep(id=1, name="Setup everything", ...),  # 太宽泛
]

# ❌ BAD: 步骤过小，过度拆分
steps = [
    DeploymentStep(id=1, name="cd ~/app", ...),  # 太细
    DeploymentStep(id=2, name="ls -la", ...),     # 太细
]
```

**原则**：每个步骤应该是一个有意义的部署单元。

---

## 错误处理

### 步骤失败处理

当步骤失败时，Orchestrator 会询问用户：

```
? Step 'Build Docker image' failed: Docker daemon not running
  What would you like to do?
  > Retry this step
    Skip and continue
    Abort deployment
```

**选项说明**：

| 选项 | 行为 | 适用场景 |
|------|------|----------|
| Retry | 重新执行此步骤 | 临时错误（如网络超时） |
| Skip | 跳过此步骤，继续后续步骤 | 可选步骤（如安装某个工具） |
| Abort | 终止部署 | 关键步骤失败，无法继续 |

---

### 超时处理

```python
# 规划阶段超时
planner = DeploymentPlanner(
    config=llm_config,
    planning_timeout=60,  # 60秒内必须生成计划
)

# 步骤执行超时
orchestrator = DeploymentOrchestrator(
    llm_config=llm_config,
    session=session,
    interaction_handler=handler,
    max_iterations_per_step=10,  # 每个步骤最多10次LLM调用
)
```

---

## 高级功能

### 1. 步骤依赖

步骤可以声明依赖关系：

```python
DeploymentStep(
    id=4,
    name="Start services",
    depends_on=[1, 2, 3],  # 依赖步骤 1, 2, 3
)
```

**行为**：
- 如果依赖步骤尚未执行 → 跳过
- 如果依赖步骤失败 → 跳过
- 只有所有依赖步骤成功或跳过 → 执行

---

### 2. 步骤间数据共享

步骤可以通过 `outputs` 传递数据：

```python
# 步骤 A: 输出数据
{"action": "step_done", "message": "...", "outputs": {"db_port": 5432}}

# 步骤 B: 访问共享数据
deploy_ctx.shared_data["db_port"]  # 5432
```

**示例场景**：
- 步骤 1：启动数据库，输出端口
- 步骤 2：配置应用，使用步骤 1 的端口

---

### 3. 用户交互

LLM 可以在步骤中询问用户：

```python
# LLM 请求
{
    "action": "ask_user",
    "question": "Which port should the app run on?",
    "options": ["3000", "8080", "5000"],
    "reasoning": "Multiple ports available"
}

# 用户响应后，LLM 在下次迭代中可以看到用户回复
```

---

## 与传统 Agent 模式对比

| 特性 | 传统模式 (enable_planning=False) | 规划模式 (enable_planning=True) |
|------|----------------------------------|----------------------------------|
| **决策方式** | 边执行边思考 | 先规划后执行 |
| **可预测性** | 低（可能迷路） | 高（有明确计划） |
| **用户体验** | 黑盒执行 | 透明（可查看计划） |
| **错误恢复** | 依赖 LLM 自我修正 | 步骤级重试/跳过 |
| **日志结构** | 扁平的命令列表 | 结构化的步骤记录 |
| **适用场景** | 简单项目 | 复杂项目 |

---

## 故障排查

### 问题 1：规划阶段超时

**症状**：
```
⚠️  Failed to create deployment plan, falling back to reactive mode
```

**原因**：
- LLM API 响应慢
- 仓库分析结果过长

**解决**：
```python
planner = DeploymentPlanner(
    config=llm_config,
    planning_timeout=120,  # 增加超时时间
)
```

---

### 问题 2：步骤一直失败

**症状**：
```
❌ Exceeded max iterations (10) for this step
```

**原因**：
- 步骤目标不明确
- 成功标准不可验证
- 环境问题（如 Docker 未安装）

**解决**：
1. 检查 `success_criteria` 是否清晰
2. 增加 `max_iterations_per_step`
3. 查看日志中的命令输出，手动修复环境

---

### 问题 3：依赖检查失败

**症状**：
```
⚠️ Skipping: dependency not met
```

**原因**：
- 依赖步骤失败或被跳过
- `depends_on` 配置错误

**解决**：
1. 检查依赖步骤的日志
2. 确认 `depends_on` 引用的步骤 ID 正确

---

## 相关文档

- [agent.md](agent.md) - 完整 Agent 文档
- [workflow.md](workflow.md) - 部署工作流
- [interaction.md](interaction.md) - 用户交互
- [orchestrator/models.py](../../src/auto_deployer/orchestrator/models.py) - 数据模型源码
- [orchestrator/prompts.py](../../src/auto_deployer/orchestrator/prompts.py) - Prompt 模板源码

---

## 总结

部署规划功能通过**两阶段设计**（规划 + 执行）显著提升了自动化部署的可靠性：

1. **规划阶段**：LLM 分析项目并生成结构化计划
2. **执行阶段**：Orchestrator 按步骤执行，每个步骤内有独立的 LLM 决策循环

**关键优势**：
- ✅ 可预测：用户可以在执行前查看完整计划
- ✅ 可控：步骤失败时可选择 Retry/Skip/Abort
- ✅ 可追踪：结构化日志记录每个步骤的执行细节
- ✅ 可扩展：支持步骤依赖、数据共享、用户交互

**推荐做法**：
- 始终启用 `enable_planning=True`
- 提供 `repo_context` 以获得更准确的计划
- 为复杂部署设置合理的 `max_iterations_per_step`

