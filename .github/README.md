# GitHub Actions & Scripts

本目录包含 GitHub Actions 工作流和辅助脚本。

## 目录结构

```
.github/
├── workflows/
│   └── run-tests.yml              # 手动触发测试的工作流
├── scripts/
│   └── generate_config.py         # 配置文件生成脚本
├── WORKFLOWS_USAGE.md             # 工作流使用文档
└── README.md                      # 本文件
```

## 快速开始

### 使用 GitHub Actions 运行测试

1. **配置 API Key**（首次使用）
   - 访问仓库 Settings → Secrets and variables → Actions
   - 添加 `AUTO_DEPLOYER_GEMINI_API_KEY` 或其他 LLM 提供商的 API Key

2. **触发工作流**
   - 访问 Actions 标签页
   - 选择 "Run Auto-Deployer Tests"
   - 点击 "Run workflow"
   - 配置参数并启动

3. **查看结果**
   - 实时查看日志输出
   - 下载生成的测试报告和日志

详细使用说明请参考 [WORKFLOWS_USAGE.md](WORKFLOWS_USAGE.md)

## 脚本说明

### generate_config.py

根据 GitHub Actions workflow inputs 动态生成配置文件。

**功能：**
- 读取 workflow 输入参数
- 加载默认配置作为基础
- 覆盖用户指定的参数
- 生成 `config/github_actions_config.json`

**环境变量：**
- `INPUT_LLM_PROVIDER`: LLM 提供商
- `INPUT_LLM_MODEL`: 模型名称
- `INPUT_TEMPERATURE`: 温度值
- `INPUT_MAX_ITERATIONS`: 最大迭代次数
- 等等...

**输出：**
- `config/github_actions_config.json`

## 工作流说明

### run-tests.yml

手动触发的测试工作流，支持完整的参数配置。

**触发方式：** `workflow_dispatch`（手动触发）

**主要步骤：**
1. 检出代码
2. 设置 Python 环境
3. 安装依赖
4. 生成配置文件
5. 配置 API Keys
6. 运行测试
7. 收集结果
8. 上传 artifacts
9. 生成摘要

**Artifacts：**
- `test-logs-[编号]`: 测试和部署日志
- `test-reports-[编号]`: 测试报告和配置

**配额消耗：**
- 运行时间：15-180 分钟（取决于配置）
- 公开仓库免费无限制
- 私有仓库每月 2000 分钟

## 本地测试工作流

在提交前测试工作流语法：

```bash
# 安装 act (GitHub Actions 本地运行工具)
# Windows: choco install act-cli
# macOS: brew install act
# Linux: 参考 https://github.com/nektos/act

# 测试工作流（dry-run）
act workflow_dispatch -n

# 实际运行（需要配置 secrets）
act workflow_dispatch --secret-file .secrets
```

## 维护指南

### 更新工作流

修改 `workflows/run-tests.yml` 后：
1. 检查 YAML 语法
2. 验证所有必需的 inputs 已定义
3. 确保 secrets 正确引用
4. 更新 `WORKFLOWS_USAGE.md` 文档

### 更新配置生成脚本

修改 `scripts/generate_config.py` 后：
1. 确保所有环境变量正确读取
2. 验证类型转换逻辑
3. 测试默认值处理
4. 更新注释和文档

### 添加新参数

1. 在 `run-tests.yml` 的 `inputs` 部分添加新参数
2. 在 `generate_config.py` 中添加对应的环境变量读取
3. 更新 `WORKFLOWS_USAGE.md` 文档
4. 在工作流的配置步骤中传递环境变量

## 故障排查

### 常见问题

**问题：API Key 未配置**
```
❌ 错误: GEMINI_API_KEY 未配置
```
解决：在仓库 Secrets 中添加对应的 API Key

**问题：配置文件生成失败**
```
❌ 错误: 无法读取默认配置
```
解决：检查 `config/default_config.json` 是否存在且格式正确

**问题：测试超时**
```
Error: The operation was canceled.
```
解决：增加 `timeout_minutes` 参数值

**问题：Artifacts 上传失败**
```
Warning: No files were found with the provided path
```
解决：检查测试是否生成了预期的日志和报告文件

### 调试技巧

1. **启用调试日志**
   - 在仓库 Settings → Secrets 添加 `ACTIONS_STEP_DEBUG=true`
   - 重新运行工作流查看详细日志

2. **本地测试配置生成**
   ```bash
   export INPUT_LLM_PROVIDER=gemini
   export INPUT_LLM_MODEL=gemini-2.0-flash-exp
   python .github/scripts/generate_config.py
   ```

3. **验证生成的配置**
   - 下载 artifacts 中的 `config/github_actions_config.json`
   - 检查参数是否正确应用

## 相关资源

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Workflow 语法](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
- [Secrets 管理](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [Artifacts 使用](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)

---

最后更新：2025-12-21
