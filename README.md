# Auto-Deployer

Auto-Deployer 是一个 LLM 驱动的自动化部署工具。只需提供 Git 仓库 URL，它就能自主分析项目、生成部署计划并完成部署。支持 SSH 远程部署和本地部署两种模式。



## 支持的项目类型与部署效果

### 🎯 支持的项目类型

Auto-Deployer 可以智能识别并部署多种类型的项目：

| 项目类型       | 支持的框架/技术                          | 部署策略                | 状态      |
| -------------- | ---------------------------------------- | ----------------------- | --------- |
| **Python**     | Flask, Django, FastAPI                   | Traditional / Docker    | ✅ 已验证 |
| **Node.js**    | Express, Next.js, Nuxt, Vue, React, Vite | Traditional / Docker    | ✅ 已验证 |
| **静态网站**   | HTML, Hugo, Jekyll                       | Static / Nginx          | ✅ 已验证 |
| **容器化项目** | Dockerfile, docker-compose.yml           | Docker / Docker-Compose | ✅ 已验证 |
| **Go**         | 标准 Go 项目                             | Traditional / Docker    | ✅ 支持   |
| **Rust**       | Cargo 项目                               | Traditional / Docker    | ✅ 支持   |
| **Java**       | Maven, Gradle                            | Traditional / Docker    | ✅ 支持   |


### 📊 部署效果统计

基于真实项目的自动化测试结果（本地部署模式）(使用grok-code Fast1作为基座模型测试)：

| 指标             | 数据     | 说明                                      |
| ---------------- | -------- | ----------------------------------------- |
| **整体成功率**   | ~70%     | 基于多个公开仓库的测试                    |
| **平均部署时间** | 5-10 分钟 | 简单项目约 3-5 分钟，复杂项目 10-15 分钟   |
| **平均迭代次数** | 20-40 次   | LLM Agent 的决策和执行迭代                |                 |
| **策略准确率**   | ~95%     | 正确选择部署策略（Docker/Traditional 等） |
| **自动修复率**   | ~60%     | 遇到错误时成功自我修复的比例              |

部署一个项目平均花费约为 $0.2

### 📝 典型部署案例

以下是实际测试通过的项目示例：

| 项目                | 类型    | 部署时间 | 迭代次数 | 状态          |
| ------------------- | -------  | -------- | -------- | ------------- |
| Express.js 官方仓库 | Node.js | ~5 分钟  | 10 次     | ✅ 成功       |
| Flask 官方仓库      | Python  | ~4 分钟  | 12 次     | ✅ 成功       |
| Next.js 博客项目    | Node.js | ~6 分钟  | 20 次     | ✅ 成功       |
| Hugo 静态站点       | Static  | ~8 分钟  | 30 次     | ✅ 成功       |
| Docker 欢迎页面     | Docker  | ~5 分钟  | 15 次     |  ✅ 成功       |
| Hugo 静态站点       | Static  | ~15 分钟(下载组件耗时久)  | 10 次     | ✅ 成功       |


### ⚡ 性能特点

- **快速分析**：本地克隆并分析仓库，通常 10-30 秒完成
- **智能规划**：生成结构化部署计划，通常 5-15 秒
- **增量部署**：重复部署时会跳过已安装的依赖
- **资源优化**：自动检测并复用已有环境（Node.js、Python 等）
## 工作原理

Auto-Deployer 采用**两阶段部署模式**：先规划后执行，确保部署过程可预测、可控制。

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   本地预分析     │ ──▶ │   连接建立      │ ──▶ │   规划阶段      │ ──▶ │   执行阶段      │
│  克隆 + 读取     │     │  SSH/本地探测   │     │  LLM 生成计划   │     │  按步骤执行     │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

1. **本地预分析**：克隆仓库到本地，读取关键文件（README、package.json、requirements.txt、Dockerfile 等），识别项目类型和框架
2. **连接建立**：建立到目标环境的连接（SSH 远程服务器或本地），收集主机信息（操作系统、内核版本等）
3. **规划阶段**：LLM 分析项目并生成结构化的部署计划（策略选择、步骤拆解、风险识别）
4. **执行阶段**：按计划逐步执行，每个步骤内 LLM 自主决策，支持步骤级重试/跳过

## 特性

- 🤖 **全自动部署**：LLM Agent 模式，无需人工干预
- 📋 **智能规划**：两阶段部署（规划+执行），执行前生成完整部署计划，可预览和确认
- 📦 **智能分析**：自动识别项目类型（Python/Node.js/静态网站等）和框架
- 🔄 **自我修复**：遇到错误时 LLM 会分析日志并尝试修复
- 🎯 **步骤化执行**：将部署拆解为原子步骤，支持步骤级重试/跳过/中止
- 💬 **用户交互**：关键决策点可询问用户（端口选择、配置值等）
- 📝 **详细日志**：每次部署的完整对话记录保存为 JSON 文件，包含计划、步骤、命令历史
- 🔧 **灵活配置**：支持环境变量和配置文件
- 🖥️ **多平台支持**：支持 SSH 远程部署（Linux）和本地部署（Windows/Linux/Mac）



## 快速开始

## 要求

- Python 3.10+
- 支持的 LLM 提供商：Gemini, OpenAI, anthropic, deepseek, openrouter.

## 安装

```bash
git clone https://github.com/ctfy66/Auto-Deployer.git
cd Auto-Deployer
pip install -e .
```



### 1. 配置环境变量

创建 `.env` 文件（或直接设置环境变量）：

```bash
# LLM API 密钥
AUTO_DEPLOYER_GEMINI_API_KEY=your-gemini-api-key

# SSH 目标服务器（可选，也可通过命令行指定）
AUTO_DEPLOYER_SSH_HOST=192.168.1.100
AUTO_DEPLOYER_SSH_USERNAME=deploy
AUTO_DEPLOYER_SSH_PASSWORD=yourpassword

# 代理设置（可选）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

### 2. 运行部署

#### SSH 远程部署

```bash
auto-deployer deploy \
    --repo git@github.com:username/project.git \
    --host 192.168.1.100 \
    --user deploy \
    --auth-method password \
    --password yourpassword
```

#### 本地部署（无需 SSH）

```bash
auto-deployer deploy \
    --repo git@github.com:username/project.git \
    --local
```

本地部署会在当前机器上执行，支持 Windows（PowerShell）和 Linux/Mac（Bash）。

### 3. 查看日志

```bash
# 列出所有部署日志
auto-deployer logs --list

# 查看最近一次部署
auto-deployer logs

# 查看特定日志
auto-deployer logs --file deploy_project_20251202_120000.json
```

## 配置

配置文件位于 `config/default_config.json`：


### LLM 提供商

| 提供商             | 配置                              | 推荐模型                                                        | 环境变量                           |
| ------------------ | --------------------------------- | --------------------------------------------------------------- | ---------------------------------- |
| **Gemini**（推荐） | `"provider": "gemini"`            | `gemini-2.0-flash-exp`<br/>`gemini-1.5-pro`                     | `AUTO_DEPLOYER_GEMINI_API_KEY`     |
| **OpenAI**         | `"provider": "openai"`            | `gpt-4o`<br/>`gpt-4o-mini`                                      | `AUTO_DEPLOYER_OPENAI_API_KEY`     |
| **Anthropic**      | `"provider": "anthropic"`         | `claude-3-5-sonnet-20241022`<br/>`claude-3-opus-20240229`       | `AUTO_DEPLOYER_ANTHROPIC_API_KEY`  |
| **DeepSeek**       | `"provider": "deepseek"`          | `deepseek-chat`<br/>`deepseek-coder`                            | `AUTO_DEPLOYER_DEEPSEEK_API_KEY`   |
| **OpenRouter**     | `"provider": "openrouter"`        | `anthropic/claude-3.5-sonnet`<br/>`google/gemini-2.0-flash-exp` | `AUTO_DEPLOYER_OPENROUTER_API_KEY` |
| **OpenAI 兼容**    | `"provider": "openai-compatible"` | 取决于端点（Ollama、LM Studio 等）                              | `AUTO_DEPLOYER_LLM_API_KEY`        |

**推荐配置**：

- **最佳性价比**：`grok Code Fast 1`
- **本地部署**：使用 OpenAI 兼容模式连接 Ollama、LM Studio 等本地模型

### 高级配置

#### Agent 行为配置

在 `config/default_config.json` 的 `agent` 部分可配置 Agent 行为：

| 配置项                    | 默认值 | 说明                       | 影响                             |
| ------------------------- | ------ | -------------------------- | -------------------------------- |
| `max_iterations`          | 180    | Agent 最大迭代次数         | 控制整个部署过程的最大执行步骤   |
| `max_iterations_per_step` | 30     | 单个步骤最大迭代次数       | 防止在某个步骤上无限循环         |
| `use_orchestrator`        | true   | 是否使用编排器（规划模式） | 启用后会先生成计划再执行         |
| `require_plan_approval`   | false  | 是否需要批准计划           | 启用后会在执行前要求用户确认     |
| `planning_timeout`        | 60     | 规划阶段超时（秒）         | 防止规划阶段耗时过长             |
| `compression_threshold`   | 0.5    | 上下文压缩阈值（0-1）      | 当上下文使用率超过此值时触发压缩 |
| `compression_keep_ratio`  | 0.3    | 压缩保留比例（0-1）        | 压缩时保留多少比例的重要信息     |

#### 循环检测配置

Agent 内置循环检测机制，防止重复执行相同操作：

| 配置项                                        | 默认值          | 说明                       |
| --------------------------------------------- | --------------- | -------------------------- |
| `loop_detection.enabled`                      | true            | 是否启用循环检测           |
| `loop_detection.direct_repeat_threshold`      | 3               | 直接重复命令阈值           |
| `loop_detection.error_loop_threshold`         | 4               | 错误循环阈值               |
| `loop_detection.command_similarity_threshold` | 0.85            | 命令相似度阈值（0-1）      |
| `loop_detection.output_similarity_threshold`  | 0.8             | 输出相似度阈值（0-1）      |
| `loop_detection.temperature_boost_levels`     | [0.3, 0.5, 0.7] | 检测到循环后的温度提升级别 |

**工作原理**：当检测到 Agent 重复执行相似命令或陷入错误循环时，自动提升 LLM temperature 以增加随机性，帮助跳出循环。

#### 交互模式配置

控制 Agent 与用户的交互方式：

| 模式       | 说明                       | 适用场景                 |
| ---------- | -------------------------- | ------------------------ |
| `cli`      | 命令行交互模式（默认）     | 需要人工监督和决策的部署 |
| `auto`     | 自动模式，自动选择默认选项 | 无人值守的自动化部署     |
| `callback` | 回调模式                   | GUI/Web 应用集成         |

配置示例：

```json
{
  "interaction": {
    "enabled": true,
    "mode": "cli"
  }
}
```

#### 代理设置

如果需要通过代理访问 LLM API：

```json
{
  "llm": {
    "proxy": "http://127.0.0.1:7890"
  }
}
```

或使用环境变量：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

### SSH 认证方式

- **密码认证**：`--auth-method password --password yourpassword`
- **密钥认证**：`--auth-method key --key-path ~/.ssh/id_rsa`

## 命令行参数

### deploy 命令

```
auto-deployer deploy [OPTIONS]

必需参数：
  --repo        Git 仓库 URL（支持 SSH 和 HTTPS）

远程部署必需：
  --host        目标服务器地址
  --user        SSH 用户名
  --auth-method 认证方式：password 或 key

可选参数：
  --local, -L   本地部署模式（无需 SSH）
  --deploy-dir  目标部署目录（默认：~/<repo_name>）
  --port        SSH 端口（默认 22，仅远程部署）
  --password    SSH 密码（auth-method=password 时）
  --key-path    SSH 私钥路径（auth-method=key 时）
  --config      自定义配置文件路径
  --workspace   本地工作目录
```

### logs 命令

```bash
# 列出所有部署日志
auto-deployer logs --list

# 查看最近一次部署
auto-deployer logs --latest

# 查看特定日志
auto-deployer logs --file deploy_project_20251202_120000.json

# 仅显示摘要
auto-deployer logs --latest --summary
```

## 项目结构

```
src/auto_deployer/
├── cli.py              # 命令行接口
├── config.py           # 配置管理
├── workflow.py         # 部署工作流
├── analyzer/           # 仓库分析模块
│   └── repo_analyzer.py
├── llm/                # LLM 提供商
│   ├── agent.py        # Agent 核心逻辑（包含规划功能）
│   ├── gemini.py
│   └── openai.py
├── orchestrator/       # 部署规划与编排
│   ├── orchestrator.py # 部署编排器
│   ├── step_executor.py# 步骤执行器
│   ├── models.py       # 数据模型
│   └── prompts.py      # Prompt 模板
├── ssh/                # SSH 会话管理
│   ├── session.py
│   └── probe.py
├── local/              # 本地会话管理
│   ├── session.py
│   └── probe.py
├── interaction/        # 用户交互处理
│   └── handler.py
├── knowledge/          # 经验存储与检索（可选）
│   ├── store.py
│   └── retriever.py
└── workspace/          # 工作空间管理
    └── manager.py
```

## 部署模式

### 规划模式（推荐）

默认启用，两阶段部署：

1. **规划阶段**：LLM 分析项目并生成结构化部署计划
2. **执行阶段**：按计划逐步执行，每个步骤内 LLM 自主决策

**优势**：

- ✅ 可预测：执行前可查看完整计划
- ✅ 可控制：步骤失败时可选择重试/跳过/中止
- ✅ 可追踪：结构化日志记录每个步骤的执行细节

## 文档

- 📖 [模块参考文档](docs/modules/index.md) - 完整的 API 参考
- 📋 [部署规划功能](docs/modules/deployment-planning.md) - 规划功能的详细说明
- 💡 [使用示例](docs/examples/deployment-planning-example.md) - 实际使用场景
- 🏗️ [架构设计](docs/architecture.md) - 系统架构说明
- ⌨️ [CLI 参考](docs/cli-reference.md) - 命令行详细说明

## License

MIT
