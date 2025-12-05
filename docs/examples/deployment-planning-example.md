# 部署规划功能使用示例

本文档展示如何使用 Auto-Deployer 的部署规划功能。

---

## 场景 1：使用 Agent 内置规划（推荐）

最简单的方式，Agent 会自动生成计划并执行。

```python
#!/usr/bin/env python3
"""使用 Agent 内置规划功能部署项目"""

from auto_deployer import load_config
from auto_deployer.llm.agent import DeploymentAgent
from auto_deployer.ssh import SSHSession, SSHCredentials
from auto_deployer.workflow import DeploymentRequest
from auto_deployer.analyzer import RepoAnalyzer

# 1. 加载配置
config = load_config()

# 2. 创建 Agent（启用规划）
agent = DeploymentAgent(
    config=config.llm,
    max_iterations=30,
    log_dir="./logs",
    enable_planning=True,           # ✅ 启用规划阶段
    require_plan_approval=True,     # ✅ 显示计划并请求用户确认
    planning_timeout=60,
)

# 3. 预先分析仓库（推荐）
analyzer = RepoAnalyzer()
repo_context = analyzer.analyze("https://github.com/user/myapp.git")

print(f"检测到项目类型: {repo_context.project_type}")
print(f"检测到框架: {repo_context.detected_framework}")

# 4. 创建 SSH 会话
creds = SSHCredentials(
    host="192.168.1.100",
    username="deploy",
    auth_method="password",
    password="your-password",
)
session = SSHSession(creds)
session.connect()

# 5. 创建部署请求
request = DeploymentRequest(
    repo_url="https://github.com/user/myapp.git",
    host="192.168.1.100",
    username="deploy",
    auth_method="password",
    password="your-password",
    deploy_dir="~/myapp",
)

# 6. 执行部署（自动规划 + 执行）
print("\n开始部署...")
success = agent.deploy(
    request=request,
    host_facts=None,  # 可选：提供主机信息
    ssh_session=session,
    repo_context=repo_context,  # ✅ 提供仓库分析结果
)

# 7. 输出结果
if success:
    print(f"✅ 部署成功")
    print(f"📄 日志文件: {agent.current_log_file}")
else:
    print(f"❌ 部署失败")
    print(f"📄 日志文件: {agent.current_log_file}")

session.disconnect()
```

### 执行输出示例

```
检测到项目类型: nodejs
检测到框架: Next.js

开始部署...
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
   Scripts:        dev, build, start
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
      Ensure Docker Engine and Docker Compose are installed
  2. 📦 [SETUP] Clone repository
      Clone the project to ~/myapp
  3. 📦 [SETUP] Create .env file
      Copy .env.example to .env and configure
  4. 🚀 [DEPLOY] Start services
      Launch services with docker-compose up -d
  5. ✅ [VERIFY] Verify deployment
      Check application responds with HTTP 200

⚠️  Identified Risks:
  - Missing .env file - will need user to provide values
  - Port 80 might be occupied

📝 Notes:
  - Application will be accessible on http://192.168.1.100:3000

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
   ✅ Step completed: Repository cloned to ~/myapp

📍 Step 3/5: Create .env file (Iteration 1)
   💬 Asking user: What should be the value for DATABASE_URL in .env?
   User replied: postgresql://user:pass@db:5432/mydb
   🔧 [1] cd ~/myapp && cp .env.example .env
      ✓ Exit code: 0
   🔧 [2] sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://user:pass@db:5432/mydb|' .env
      ✓ Exit code: 0
   ✅ Step completed: .env file created

📍 Step 4/5: Start services (Iteration 1)
   🔧 [1] cd ~/myapp && docker-compose up -d --build
      ✓ Exit code: 0
   ✅ Step completed: All services started

📍 Step 5/5: Verify deployment (Iteration 1)
   🔧 [1] curl -s -o /dev/null -w "%{http_code}" http://192.168.1.100:3000
      ✓ Exit code: 0 (HTTP 200)
   ✅ Step completed: Application is responding

============================================================
✅ Agent completed: Application deployed successfully on http://192.168.1.100:3000
📄 Log saved to: ./logs/deploy_myapp_20241205_120000.json
============================================================
```

---

## 场景 2：分离规划和执行（高级）

手动分离规划和执行阶段，适合需要自定义逻辑的场景。

```python
#!/usr/bin/env python3
"""手动分离规划和执行阶段"""

from auto_deployer import load_config
from auto_deployer.llm.agent import DeploymentPlanner
from auto_deployer.orchestrator import DeploymentOrchestrator
from auto_deployer.orchestrator.models import DeployContext
from auto_deployer.ssh import SSHSession, SSHCredentials
from auto_deployer.analyzer import RepoAnalyzer
from auto_deployer.interaction import CLIInteractionHandler
import json

# 1. 配置
config = load_config()

# 2. 分析仓库
analyzer = RepoAnalyzer()
repo_context = analyzer.analyze("https://github.com/user/myapp.git")

# 3. 创建规划器
planner = DeploymentPlanner(
    config=config.llm,
    planning_timeout=60,
)

# 4. 生成部署计划
print("📋 生成部署计划...")
plan = planner.create_plan(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/myapp",
    host_info={"os_release": "Ubuntu 22.04", "kernel": "5.15.0"},
    repo_analysis=repo_context.to_prompt_context(),
    project_type=repo_context.project_type,
    framework=repo_context.detected_framework,
    is_local=False,
)

if not plan:
    print("❌ 无法生成部署计划")
    exit(1)

# 5. 显示计划
DeploymentPlanner.display_plan(plan)

# 6. 保存计划到文件（可选）
plan_file = "deployment_plan.json"
with open(plan_file, "w") as f:
    json.dump(plan.to_dict(), f, indent=2, ensure_ascii=False)
print(f"\n📄 计划已保存到: {plan_file}")

# 7. 用户确认
confirm = input("\n是否继续执行此计划? (y/n): ")
if confirm.lower() != 'y':
    print("❌ 部署已取消")
    exit(0)

# 8. 创建部署上下文
deploy_ctx = DeployContext(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/myapp",
    host_info={"os_release": "Ubuntu 22.04", "kernel": "5.15.0"},
    repo_analysis=repo_context.to_prompt_context(),
    project_type=repo_context.project_type,
    framework=repo_context.detected_framework,
)

# 9. 创建 SSH 会话
creds = SSHCredentials(
    host="192.168.1.100",
    username="deploy",
    auth_method="password",
    password="your-password",
)
session = SSHSession(creds)
session.connect()

# 10. 创建编排器
orchestrator = DeploymentOrchestrator(
    llm_config=config.llm,
    session=session,
    interaction_handler=CLIInteractionHandler(),
    log_dir="./logs",
    max_iterations_per_step=10,  # 每个步骤最多10次迭代
)

# 11. 执行计划
print("\n🚀 执行部署计划...")
success = orchestrator.run(plan, deploy_ctx)

# 12. 输出结果
if success:
    print(f"\n✅ 部署成功")
    print(f"📄 日志: {orchestrator.current_log_file}")
else:
    print(f"\n❌ 部署失败")
    print(f"📄 日志: {orchestrator.current_log_file}")

session.disconnect()
```

---

## 场景 3：本地部署

使用规划功能进行本地部署（在当前机器上部署）。

```python
#!/usr/bin/env python3
"""本地部署示例"""

from auto_deployer import load_config
from auto_deployer.llm.agent import DeploymentAgent
from auto_deployer.local import LocalSession, LocalHostFacts
from auto_deployer.workflow import LocalDeploymentRequest
from auto_deployer.analyzer import RepoAnalyzer

# 1. 配置
config = load_config()

# 2. 创建 Agent（启用规划）
agent = DeploymentAgent(
    config=config.llm,
    enable_planning=True,
    require_plan_approval=True,
)

# 3. 分析仓库
analyzer = RepoAnalyzer()
repo_context = analyzer.analyze("https://github.com/user/myapp.git")

# 4. 创建本地会话
local_session = LocalSession()

# 5. 获取本地主机信息（可选）
host_facts = LocalHostFacts.gather()
print(f"本地系统: {host_facts.os_name} {host_facts.os_release}")

# 6. 创建本地部署请求
request = LocalDeploymentRequest(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/myapp",
)

# 7. 执行本地部署
print("\n开始本地部署...")
success = agent.deploy_local(
    request=request,
    host_facts=host_facts,
    local_session=local_session,
    repo_context=repo_context,
)

if success:
    print(f"✅ 本地部署成功")
    print(f"📄 日志: {agent.current_log_file}")
else:
    print(f"❌ 本地部署失败")
    print(f"📄 日志: {agent.current_log_file}")
```

---

## 场景 4：自定义步骤处理

手动创建计划并自定义步骤处理逻辑。

```python
#!/usr/bin/env python3
"""自定义步骤处理"""

from auto_deployer import load_config
from auto_deployer.llm.agent import DeploymentPlan, DeploymentStep
from auto_deployer.orchestrator import DeploymentOrchestrator
from auto_deployer.orchestrator.models import DeployContext
from auto_deployer.ssh import SSHSession, SSHCredentials
from auto_deployer.interaction import CLIInteractionHandler

# 1. 手动创建部署计划
plan = DeploymentPlan(
    strategy="docker-compose",
    components=["docker", "docker-compose", "git"],
    steps=[
        DeploymentStep(
            id=1,
            name="检查 Docker",
            description="确认 Docker 已安装",
            category="prerequisite",
            estimated_commands=["docker --version"],
            success_criteria="docker --version 返回版本号",
            depends_on=[],
        ),
        DeploymentStep(
            id=2,
            name="克隆仓库",
            description="克隆项目到 ~/myapp",
            category="setup",
            estimated_commands=[
                "rm -rf ~/myapp",
                "git clone https://github.com/user/myapp.git ~/myapp"
            ],
            success_criteria="目录 ~/myapp 存在且包含 docker-compose.yml",
            depends_on=[],
        ),
        DeploymentStep(
            id=3,
            name="启动服务",
            description="使用 docker-compose 启动所有服务",
            category="deploy",
            estimated_commands=["cd ~/myapp && docker-compose up -d --build"],
            success_criteria="docker-compose ps 显示所有服务运行中",
            depends_on=[1, 2],  # 依赖步骤 1 和 2
        ),
        DeploymentStep(
            id=4,
            name="验证部署",
            description="检查应用是否响应",
            category="verify",
            estimated_commands=["curl -s -o /dev/null -w '%{http_code}' http://localhost:3000"],
            success_criteria="curl 返回 HTTP 200",
            depends_on=[3],  # 依赖步骤 3
        ),
    ],
    risks=[
        "Docker 可能未安装",
        "端口 3000 可能被占用",
    ],
    notes=[
        "确保服务器有足够的内存（至少 2GB）",
    ],
    estimated_time="3-5 分钟",
)

# 2. 显示计划
from auto_deployer.llm.agent import DeploymentPlanner
DeploymentPlanner.display_plan(plan)

# 3. 创建部署上下文
deploy_ctx = DeployContext(
    repo_url="https://github.com/user/myapp.git",
    deploy_dir="~/myapp",
    host_info={"os_release": "Ubuntu 22.04"},
)

# 4. 执行
config = load_config()
session = SSHSession(SSHCredentials(
    host="192.168.1.100",
    username="deploy",
    password="your-password",
))
session.connect()

orchestrator = DeploymentOrchestrator(
    llm_config=config.llm,
    session=session,
    interaction_handler=CLIInteractionHandler(),
    log_dir="./logs",
)

success = orchestrator.run(plan, deploy_ctx)

print(f"部署{'成功' if success else '失败'}")
session.disconnect()
```

---

## 场景 5：查看和分析日志

部署完成后，查看详细的日志记录。

```python
#!/usr/bin/env python3
"""查看部署日志"""

import json
from pathlib import Path

# 1. 读取最新的日志文件
log_dir = Path("./logs")
log_files = sorted(log_dir.glob("deploy_*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

if not log_files:
    print("没有找到日志文件")
    exit(1)

latest_log = log_files[0]
print(f"📄 读取日志: {latest_log}")

with open(latest_log, "r", encoding="utf-8") as f:
    log = json.load(f)

# 2. 显示基本信息
print("\n" + "=" * 60)
print("部署概览")
print("=" * 60)
print(f"仓库: {log['repo_url']}")
print(f"状态: {log['status']}")
print(f"开始时间: {log['start_time']}")
print(f"结束时间: {log['end_time']}")

# 3. 显示计划（如果有）
if 'plan' in log:
    plan = log['plan']
    print("\n" + "=" * 60)
    print("部署计划")
    print("=" * 60)
    print(f"策略: {plan['strategy']}")
    print(f"组件: {', '.join(plan['components'])}")
    print(f"预计时间: {plan['estimated_time']}")
    print(f"\n步骤数: {len(plan['steps'])}")
    for step in plan['steps']:
        print(f"  {step['id']}. [{step['category']}] {step['name']}")

# 4. 显示执行摘要
if 'summary' in log:
    summary = log['summary']
    print("\n" + "=" * 60)
    print("执行摘要")
    print("=" * 60)
    print(f"总步骤数: {summary['total_steps']}")
    print(f"成功步骤: {summary['successful_steps']}")
    print(f"总命令数: {summary['total_commands']}")
    print(f"执行时长: {summary['duration_seconds']} 秒")

# 5. 显示步骤详情
print("\n" + "=" * 60)
print("步骤执行详情")
print("=" * 60)
for step in log['steps']:
    status_emoji = {"success": "✅", "failed": "❌", "skipped": "⏭️"}.get(step['status'], "❓")
    print(f"\n{status_emoji} 步骤 {step['step_id']}: {step['step_name']}")
    print(f"   状态: {step['status']}")
    print(f"   迭代次数: {step['iterations']}")
    print(f"   命令数: {len(step['commands'])}")
    
    # 显示命令
    for i, cmd in enumerate(step['commands'], 1):
        cmd_status = "✓" if cmd['success'] else "✗"
        print(f"   {cmd_status} [{i}] {cmd['command']}")
        if not cmd['success'] and cmd['stderr']:
            print(f"       错误: {cmd['stderr'][:100]}")
    
    # 显示错误信息
    if step.get('error'):
        print(f"   ⚠️ 错误: {step['error']}")
    
    # 显示输出
    if step.get('outputs'):
        print(f"   📤 输出: {step['outputs']}")
```

### 日志输出示例

```
📄 读取日志: ./logs/deploy_myapp_20241205_120000.json

============================================================
部署概览
============================================================
仓库: https://github.com/user/myapp.git
状态: success
开始时间: 2024-12-05T12:00:00
结束时间: 2024-12-05T12:08:30

============================================================
部署计划
============================================================
策略: docker-compose
组件: docker, docker-compose
预计时间: 5-10 minutes

步骤数: 5
  1. [prerequisite] Install Docker
  2. [setup] Clone repository
  3. [setup] Create .env file
  4. [deploy] Start services
  5. [verify] Verify deployment

============================================================
执行摘要
============================================================
总步骤数: 5
成功步骤: 5
总命令数: 12
执行时长: 510 秒

============================================================
步骤执行详情
============================================================

✅ 步骤 1: Install Docker
   状态: success
   迭代次数: 3
   命令数: 2
   ✓ [1] curl -fsSL https://get.docker.com -o get-docker.sh
   ✓ [2] sudo sh get-docker.sh

✅ 步骤 2: Clone repository
   状态: success
   迭代次数: 1
   命令数: 1
   ✓ [1] git clone https://github.com/user/myapp.git ~/myapp

... (其他步骤)
```

---

## 常见问题

### Q1: 如何禁用用户确认？

```python
agent = DeploymentAgent(
    config=config.llm,
    enable_planning=True,
    require_plan_approval=False,  # ❌ 不需要用户确认
)
```

### Q2: 如何调整每个步骤的迭代次数？

```python
orchestrator = DeploymentOrchestrator(
    llm_config=config.llm,
    session=session,
    interaction_handler=handler,
    max_iterations_per_step=15,  # 增加到 15 次
)
```

### Q3: 如何在 Windows 上使用？

```python
orchestrator = DeploymentOrchestrator(
    llm_config=config.llm,
    session=local_session,
    interaction_handler=handler,
    is_windows=True,  # ✅ 启用 Windows PowerShell 支持
)
```

### Q4: 如何跳过规划阶段？

```python
agent = DeploymentAgent(
    config=config.llm,
    enable_planning=False,  # ❌ 禁用规划，回退到传统模式
)
```

---

## 更多资源

- [部署规划技术文档](../modules/deployment-planning.md) - 完整的 API 参考
- [Agent 模块文档](../modules/agent.md) - Agent 的详细说明
- [CLI 参考](../cli-reference.md) - 命令行使用方法

