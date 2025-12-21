# GitHub Actions 工作流说明

## 手动触发测试

本项目包含一个功能完整的 GitHub Actions 工作流，用于在云端运行 Auto-Deployer 测试套件。

### 📋 使用步骤

#### 1. 配置 API Keys（首次使用）

在 GitHub 仓库设置中添加 Secrets：

1. 访问仓库页面：`https://github.com/ctfy66/Auto-Deployer`
2. 点击 `Settings` → `Secrets and variables` → `Actions`
3. 点击 `New repository secret`
4. 根据使用的 LLM 提供商添加对应的 Secret：

| LLM 提供商 | Secret 名称                        |
| ---------- | ---------------------------------- |
| Gemini     | `AUTO_DEPLOYER_GEMINI_API_KEY`     |
| OpenAI     | `AUTO_DEPLOYER_OPENAI_API_KEY`     |
| Anthropic  | `AUTO_DEPLOYER_ANTHROPIC_API_KEY`  |
| DeepSeek   | `AUTO_DEPLOYER_DEEPSEEK_API_KEY`   |
| OpenRouter | `AUTO_DEPLOYER_OPENROUTER_API_KEY` |

#### 2. 触发工作流

1. 访问仓库的 `Actions` 标签页
2. 在左侧选择 `Run Auto-Deployer Tests`
3. 点击右侧的 `Run workflow` 按钮
4. 配置测试参数（见下方参数说明）
5. 点击绿色的 `Run workflow` 按钮启动

#### 3. 查看测试结果

- **实时日志**：在 Actions 页面查看运行中的测试日志
- **测试摘要**：测试完成后会在摘要页面显示关键信息
- **下载 Artifacts**：
  - `test-logs-[运行编号]`：包含测试日志和部署日志
  - `test-reports-[运行编号]`：包含测试报告和配置文件

### ⚙️ 可配置参数

#### 测试范围参数

| 参数           | 说明         | 默认值         | 可选值                          |
| -------------- | ------------ | -------------- | ------------------------------- |
| `test_mode`    | 测试模式     | `local`        | `local`, `docker`, `both`       |
| `project_name` | 特定项目名称 | 空（所有项目） | 项目名称字符串                  |
| `difficulty`   | 难度过滤     | `all`          | `all`, `easy`, `medium`, `hard` |
| `tags`         | 标签过滤     | 空             | 逗号分隔，如 `docker,nodejs`    |

#### LLM 配置参数

| 参数                      | 说明         | 默认值                 | 可选值                                                                         |
| ------------------------- | ------------ | ---------------------- | ------------------------------------------------------------------------------ |
| `llm_provider`            | LLM 提供商   | `gemini`               | `gemini`, `openai`, `anthropic`, `deepseek`, `openrouter`, `openai-compatible` |
| `llm_model`               | 模型名称     | `gemini-2.0-flash-exp` | 对应提供商的模型名                                                             |
| `temperature`             | 温度值       | `0.0`                  | `0.0` - `2.0`                                                                  |
| `max_iterations`          | 最大迭代次数 | `180`                  | 整数                                                                           |
| `max_iterations_per_step` | 每步最大迭代 | `30`                   | 整数                                                                           |

#### 部署配置参数

| 参数                       | 说明             | 默认值  |
| -------------------------- | ---------------- | ------- |
| `enable_planning`          | 启用规划阶段     | `true`  |
| `require_plan_approval`    | 需要计划批准     | `false` |
| `planning_timeout`         | 规划超时（秒）   | `60`    |
| `loop_detection_enabled`   | 启用循环检测     | `true`  |

#### 交互配置参数

| 参数                         | 说明                           | 默认值 | 可选值                |
| ---------------------------- | ------------------------------ | ------ | --------------------- |
| `interaction_enabled`        | 启用用户交互                   | `true` | `true`, `false`       |
| `interaction_mode`           | 交互模式                       | `cli`  | `cli`, `auto`, `callback` |
| `auto_retry_on_interaction` | 交互时自动重试                 | `true` | `true`, `false`       |

**交互模式说明：**
- `cli`: 交互式命令行（需要用户输入，Actions 中不适用）
- `auto`: 自动重试模式（遇到交互时自动重试，推荐用于 Actions）
- `callback`: 回调模式（用于 GUI/Web 集成）

#### 测试执行参数

| 参数              | 说明               | 默认值  |
| ----------------- | ------------------ | ------- |
| `parallel_mode`   | 并行测试           | `false` |
| `max_workers`     | 并行线程数         | `2`     |
| `skip_setup`      | 跳过环境设置       | `false` |
| `timeout_minutes` | 整体超时（分钟）   | `120`   |

#### 输出配置参数

| 参数             | 说明               | 默认值 |
| ---------------- | ------------------ | ------ |
| `upload_logs`    | 上传测试日志       | `true` |
| `upload_reports` | 上传测试报告       | `true` |
| `retention_days` | Artifacts 保留天数 | `30`   |

### 📊 测试结果结构

下载的 Artifacts 包含以下内容：

```
test-logs-[编号]/
├── logs/
│   └── test_output.log          # 完整测试输出
└── agent_logs/
    └── deploy_*.json             # 每次部署的详细日志

test-reports-[编号]/
├── reports/
│   ├── test_report.html          # HTML 格式测试报告
│   ├── test_report.json          # JSON 格式测试报告
│   └── metrics_summary.json      # 测试指标摘要
└── config/
    └── github_actions_config.json # 使用的配置文件
```

### 💡 使用技巧

#### 快速测试单个项目

```yaml
test_mode: local
project_name: docker-welcome
difficulty: easy
parallel_mode: false
timeout_minutes: 30
```

#### 完整测试所有项目

```yaml
test_mode: local
project_name: (留空)
difficulty: all
parallel_mode: true
max_workers: 4
timeout_minutes: 180
```

#### 使用不同的 LLM

```yaml
llm_provider: openai
llm_model: gpt-4o
temperature: 0.0
```

### 🔍 故障排查

**问题：工作流失败，提示 API Key 未配置**

- 解决：在仓库 Settings → Secrets 中添加对应的 API Key

**问题：测试超时**

- 解决：增加 `timeout_minutes` 参数值

**问题：找不到测试报告**

- 解决：检查 `upload_reports` 是否设置为 `true`

**问题：并行测试失败率高**

- 解决：降低 `max_workers` 值或关闭 `parallel_mode`

### 📈 配额管理

GitHub Actions 免费配额：

- 公开仓库：无限制
- 私有仓库：每月 2000 分钟

运行时间估算：

- 单个简单项目：5-10 分钟
- 所有项目（顺序）：60-120 分钟
- 所有项目（并行）：30-60 分钟

### 🛠️ 高级用法

#### 自定义模型参数

```yaml
llm_model: gpt-4o-mini
temperature: 0.3
max_iterations_per_step: 50
```

#### 调试特定难度项目

```yaml
difficulty: hard
parallel_mode: false
timeout_minutes: 180
```

#### 快速验证修改

```yaml
project_name: nodejs-express-hello
skip_setup: true
timeout_minutes: 15
```

---

更多信息请参考主 README.md 和项目文档。
