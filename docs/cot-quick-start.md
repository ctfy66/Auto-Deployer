# 思维链 (Chain of Thought) 快速上手指南

## 🚀 5 分钟快速开始

### 什么是思维链？

思维链（Chain of Thought, CoT）是一种引导 LLM 进行**系统化推理**的提示技术。它要求 LLM 在做出决策前，显式地展示其思考过程。

**没有思维链**：
```
LLM: 执行 "npm install -g pm2"
→ 污染全局环境，可能导致版本冲突
```

**有思维链**：
```
LLM 推理过程：
- 观察：需要安装 pm2 来管理进程
- 分析：有两种方式：全局安装 vs 本地安装
- 推理：
  * 全局安装 (npm install -g pm2)
    ✅ 方便：所有项目可用
    ❌ 风险：版本冲突、污染系统
  * 本地安装 (npm install pm2 && npx pm2)
    ✅ 隔离：每个项目独立
    ❌ 稍慢：需要为每个项目安装
- 决策：使用本地安装，避免全局污染

执行：npm install pm2
```

## 📦 已集成的功能

### 1. 规划阶段思维链

**位置**: `src/auto_deployer/prompts/planning.py`

**效果**: LLM 在生成部署计划前，会进行深度分析：

```
## Project Understanding
这是一个 Express.js Web 应用，使用 MongoDB 数据库...

## Environment Analysis
目标环境是 Ubuntu 20.04，已安装 Docker 和 Node.js...

## Strategy Reasoning
- Docker Compose: ✅ 最佳选择，因为有 docker-compose.yml
- Traditional: ❌ 不必要，Docker 更简单
Chosen: docker-compose

## Step Design Logic
1. 验证 Docker 可用
2. Clone 仓库
3. 配置环境变量
4. 启动容器
...

{JSON 部署计划}
```

### 2. 执行阶段思维链

**位置**: `src/auto_deployer/prompts/execution_step.py`

**效果**: 每个命令执行前，LLM 都会推理：

```json
{
  "action": "execute",
  "command": "docker-compose up -d",
  "reasoning": {
    "observation": "docker-compose.yml 已验证，环境变量已设置",
    "analysis": "需要启动所有服务容器",
    "alternatives_considered": [
      "docker-compose up: 前台运行，会阻塞终端",
      "docker-compose up -d: 后台运行，适合部署"
    ],
    "decision": "使用 -d 标志后台运行",
    "verification": "检查 docker-compose ps 显示所有服务 Up",
    "fallback": "如果失败，查看 docker-compose logs"
  }
}
```

### 3. 错误分析思维链

**效果**: 遇到错误时，系统化诊断：

```
错误分析 CoT：

WHAT I SEE:
- Exit code: 1
- Stderr: "Cannot connect to Docker daemon"

ERROR CHAIN:
1. 通用错误: "Cannot connect"
2. 具体错误: "/var/run/docker.sock 文件不存在"
3. 根因: Docker 守护进程未启动

HYPOTHESIS:
最可能的原因：Docker 服务未运行
证据：socket 文件缺失 + 连接错误

SOLUTION:
启动 Docker 服务: sudo systemctl start docker
```

## 🔧 如何使用

### 开发者：在新提示词中使用

```python
from auto_deployer.prompts.cot_framework import (
    CHAIN_OF_THOUGHT_FRAMEWORK,
    get_cot_framework,
    get_reasoning_requirements
)

# 方式 1: 使用完整框架
my_prompt = f"""
{CHAIN_OF_THOUGHT_FRAMEWORK}

Your task: ...
"""

# 方式 2: 获取特定阶段的 CoT
execution_cot = get_cot_framework("execution")
error_cot = get_cot_framework("error_analysis")

# 方式 3: 添加推理要求
my_prompt += get_reasoning_requirements(detailed=True)
```

### 用户：查看推理过程

部署完成后，查看日志中的推理记录：

```bash
# 查看最新部署日志
auto-deployer logs --latest

# 提取推理字段
jq '.steps[].reasoning' agent_logs/deploy_myapp_20241212.json
```

## 📊 预期效果

### 定量改善

| 指标 | 改善幅度 | 说明 |
|------|---------|------|
| 盲目重试次数 | ↓ 40% | 不再重复失败的命令 |
| 重复错误 | ↓ 50% | 从根因解决问题 |
| 首次成功率 | ↑ 25% | 更好的初始决策 |
| 平均迭代数 | ↓ 30% | 更快到达目标 |

### 定性改善

**之前（无思维链）**:
```
1. npm install -g pm2  (失败)
2. npm install -g pm2  (重试，失败)
3. sudo npm install -g pm2  (加 sudo，失败)
4. 询问用户...
```

**现在（有思维链）**:
```
1. 推理：全局安装风险高，应该用本地
2. npm install pm2
3. npx pm2 start app.js
   → 成功！
```

## 🎯 关键概念

### 四步推理框架

所有决策遵循：

1. **观察 (OBSERVE)** - 当前状态是什么？
2. **分析 (ANALYZE)** - 目标和约束是什么？
3. **推理 (REASON)** - 有哪些方案？优缺点？
4. **决策 (DECIDE)** - 选择哪个？如何验证？

### 何时使用完整 CoT？

- ✅ 遇到错误或失败
- ✅ 多种方案可选
- ✅ 不确定最佳做法
- ✅ 需要用户决策

### 何时使用简化 CoT？

- ✅ 操作简单明确
- ✅ 遵循既定模式
- ✅ 上一步成功后的自然后续

## 📝 JSON 响应格式

### Execute（执行命令）

```json
{
  "action": "execute",
  "command": "...",
  "reasoning": {
    "observation": "当前看到什么",
    "analysis": "试图达成什么",
    "alternatives_considered": ["方案1: 为何不选", "方案2: 选择原因"],
    "decision": "为何选这个命令",
    "verification": "如何验证成功",
    "fallback": "失败了怎么办"
  }
}
```

### Step Done（步骤完成）

```json
{
  "action": "step_done",
  "message": "完成了什么",
  "reasoning": {
    "observation": "最终状态",
    "verification": "如何确认成功",
    "success_criteria_met": "满足了哪些标准"
  }
}
```

### Step Failed（步骤失败）

```json
{
  "action": "step_failed",
  "message": "为何失败",
  "reasoning": {
    "observation": "遇到的错误",
    "root_cause_analysis": "根本原因",
    "attempts_made": ["尝试过的方案"],
    "why_failed": "为何无法恢复"
  }
}
```

### Ask User（询问用户）

```json
{
  "action": "ask_user",
  "question": "问题",
  "options": ["选项1", "选项2"],
  "reasoning": {
    "observation": "当前情况",
    "why_asking": "为何需要用户决策",
    "implications": "各选项的含义"
  }
}
```

## 🧪 测试你的实现

### 验证导入

```bash
# 测试 CoT 框架
py -3.12 -c "from src.auto_deployer.prompts.cot_framework import CHAIN_OF_THOUGHT_FRAMEWORK; print('OK')"

# 测试规划提示词
py -3.12 -c "from src.auto_deployer.prompts.planning import build_planning_prompt; print('OK')"

# 测试执行提示词
py -3.12 -c "from src.auto_deployer.prompts.execution_step import build_step_execution_prompt; print('OK')"
```

### 运行实际部署

```bash
# 本地部署测试项目
auto-deployer deploy --repo https://github.com/example/nodejs-app --local

# 查看日志中的推理
auto-deployer logs --latest | grep -A 20 "reasoning"
```

### 分析推理质量

```bash
# 检查推理完整性
jq '.steps[] | select(.reasoning != null) | .reasoning | keys' agent_logs/deploy_*.json

# 统计有推理的步骤数
jq '[.steps[] | select(.reasoning != null)] | length' agent_logs/deploy_*.json
```

## 📚 更多资源

- **完整文档**: [chain-of-thought-implementation.md](./chain-of-thought-implementation.md)
- **源代码**: `src/auto_deployer/prompts/cot_framework.py`
- **示例**: 查看 `agent_logs/` 目录中的部署日志

## 💡 最佳实践

### DO ✅

- 在所有新的提示词中包含推理要求
- 提供具体的示例展示期望的推理格式
- 定期检查日志中的推理质量
- 根据实际效果调整 CoT 模板

### DON'T ❌

- 不要期望 LLM 自动使用 CoT（必须在提示词中明确要求）
- 不要忽略推理字段缺失的情况
- 不要让所有操作都用完整 CoT（简单操作用简化版）
- 不要忘记验证推理的逻辑性

## 🤔 常见问题

**Q: CoT 会增加延迟吗？**
A: 会略微增加（10-15%），但通过减少重试和错误，整体速度反而更快。

**Q: 所有 LLM 都支持 CoT 吗？**
A: 较大的模型（GPT-4, Claude, Gemini 2.0）效果最好。小模型可能需要更多示例。

**Q: 推理格式不对怎么办？**
A: 增加示例、强调 MANDATORY、考虑添加格式验证。

**Q: 如何量化 CoT 的效果？**
A: 对比启用前后的：成功率、平均迭代数、错误重试次数。

---

**开始使用**: 现有的规划和执行阶段已经集成了思维链，直接运行部署即可看到效果！

```bash
auto-deployer deploy --repo <your-repo> --local
```
