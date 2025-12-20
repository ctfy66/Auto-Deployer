# Agent 模块

部署规划和步骤执行的核心模块。

**模块路径**：`auto_deployer.llm.agent`

---

## 概述

`agent` 模块提供部署规划功能，通过LLM生成结构化的部署计划。该计划随后由Orchestrator模块按步骤执行。

---

## 类

### DeploymentStep

部署计划中的单个步骤。

```python
@dataclass
class DeploymentStep:
    id: int
    name: str
    description: str
    category: str
    estimated_commands: List[str] = field(default_factory=list)
    success_criteria: str = ""
    depends_on: List[int] = field(default_factory=list)
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | `int` | 步骤唯一ID |
| `name` | `str` | 步骤名称，如 "Install Node.js" |
| `description` | `str` | 详细描述 |
| `category` | `str` | 类别：`prerequisite`、`setup`、`build`、`deploy`、`verify` |
| `estimated_commands` | `List[str]` | 预计执行的命令（仅供参考） |
| `success_criteria` | `str` | 成功标准描述 |
| `depends_on` | `List[int]` | 依赖的步骤ID列表 |

---

### DeploymentPlan

完整的部署方案。

```python
@dataclass
class DeploymentPlan:
    strategy: str
    components: List[str] = field(default_factory=list)
    steps: List[DeploymentStep] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    estimated_time: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `strategy` | `str` | 部署策略：`docker-compose`、`docker`、`traditional`、`static` |
| `components` | `List[str]` | 所需组件列表，如 `["nodejs", "nginx", "pm2"]` |
| `steps` | `List[DeploymentStep]` | 有序的部署步骤列表 |
| `risks` | `List[str]` | 已识别的风险列表 |
| `notes` | `List[str]` | 注意事项 |
| `estimated_time` | `str` | 预计执行时间 |
| `created_at` | `str` | 创建时间（ISO格式） |

#### 方法

**`to_dict() -> dict`**

将计划转换为字典格式，用于日志记录。

---

### DeploymentPlanner

部署计划生成器。

```python
class DeploymentPlanner:
    def __init__(
        self,
        config: LLMConfig,
        planning_timeout: int = 60,
    ) -> None: ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `config` | `LLMConfig` | LLM配置（必须包含 `api_key`） |
| `planning_timeout` | `int` | 规划超时时间（秒），默认60 |

#### 方法

**`create_plan(...) -> Optional[DeploymentPlan]`**

创建结构化的部署计划。

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
) -> Optional[DeploymentPlan]:
```

**参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `repo_url` | `str` | 仓库URL |
| `deploy_dir` | `str` | 目标部署目录 |
| `host_info` | `dict` | 主机信息字典 |
| `repo_analysis` | `Optional[str]` | 预分析的仓库上下文 |
| `project_type` | `Optional[str]` | 检测到的项目类型 |
| `framework` | `Optional[str]` | 检测到的框架 |
| `is_local` | `bool` | 是否本地部署 |

**返回：**
- 成功时返回 `DeploymentPlan`
- 失败时返回 `None`

**`display_plan(plan: DeploymentPlan) -> None`** (静态方法)

以可读格式显示部署计划。

---

## 工作流程

### 规划阶段

```
1. 收集上下文信息
   ├─ 仓库信息（语言、框架、依赖）
   ├─ 主机信息（OS、可用工具）
   └─ 项目分析结果

2. 调用LLM生成计划
   └─ 使用 prompts/planning.py 中的提示模板
   └─ LLM返回结构化JSON

3. 解析和验证计划
   ├─ 提取JSON内容
   ├─ 验证必需字段（strategy, steps）
   └─ 构建DeploymentPlan对象

4. 显示计划给用户
   └─ 包括策略、组件、步骤、风险、预估时间

5. (可选) 用户确认
   └─ 如果 require_plan_approval=true
```

### 示例输出

```
================================================================================
📋 DEPLOYMENT PLAN
================================================================================
Strategy: docker-compose
Components: docker, docker-compose
Estimated Time: 5-10 minutes
Total Steps: 4

⚠️  Identified Risks:
  - Docker service must be running
  - Port 3000 may be in use

📝 Notes:
  - Using existing docker-compose.yml
  - Application will run in detached mode

📍 Deployment Steps:
--------------------------------------------------------------------------------

1. Verify Docker Installation [prerequisite]
   Check if Docker and Docker Compose are installed
   Success: Docker version displayed successfully

2. Clone Repository [setup]
   Clone the repository to deployment directory
   Depends on: Step(s) 1

3. Build and Start Services [deploy]
   Run docker-compose up -d to start services
   Depends on: Step(s) 2

4. Verify Deployment [verify]
   Check if application is responding on port 3000
   Depends on: Step(s) 3

================================================================================
```

---

## 与其他模块的关系

- **workflow.py**: 调用 `DeploymentPlanner` 生成计划
- **orchestrator**: 接收 `DeploymentPlan` 并执行步骤
- **prompts/planning.py**: 提供规划阶段的LLM提示模板
- **config**: 读取 `planning_timeout` 和 `require_plan_approval` 配置

---

## 配置

规划器相关配置位于 `config/default_config.json`:

```json
{
  "agent": {
    "require_plan_approval": false,
    "planning_timeout": 60
  }
}
```

- **`require_plan_approval`**: 是否需要用户批准计划后才执行
- **`planning_timeout`**: LLM生成计划的超时时间（秒）
