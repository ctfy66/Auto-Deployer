# 🚀 GitHub Actions 快速开始指南

5 分钟内在 GitHub Actions 上运行 Auto-Deployer 测试！

## 📋 前置条件

- ✅ GitHub 账户
- ✅ 访问此仓库的权限
- ✅ LLM API Key（Gemini/OpenAI/Anthropic 等）

## 🎯 三步快速开始

### 步骤 1️⃣：配置 API Key（2 分钟）

1. 打开仓库页面：https://github.com/ctfy66/Auto-Deployer
2. 点击 **Settings** 标签
3. 左侧菜单选择 **Secrets and variables** → **Actions**
4. 点击绿色按钮 **New repository secret**
5. 添加 Secret：
   - **Name**: `AUTO_DEPLOYER_GEMINI_API_KEY`（或其他提供商）
   - **Value**: 粘贴你的 API Key
6. 点击 **Add secret**

✨ **提示**：只需配置你要使用的 LLM 提供商的 API Key

### 步骤 2️⃣：触发测试工作流（1 分钟）

1. 点击仓库页面的 **Actions** 标签
2. 左侧选择 **Run Auto-Deployer Tests**
3. 右侧点击 **Run workflow** 下拉按钮
4. 保持默认配置（或按需调整）
5. 点击绿色的 **Run workflow** 按钮

🎉 测试已开始运行！

### 步骤 3️⃣：查看结果（2 分钟）

1. 等待测试完成（通常 5-30 分钟）
2. 点击工作流运行记录查看实时日志
3. 测试完成后，滚动到页面底部
4. 在 **Artifacts** 部分下载：
   - **test-logs-[编号]**：完整日志
   - **test-reports-[编号]**：测试报告

## 🎨 推荐配置

### 快速测试（5-10 分钟）

```yaml
测试模式: local
项目名称: docker-welcome
难度过滤: easy
并行测试: false
超时时间: 30 分钟
```

### 完整测试（60-120 分钟）

```yaml
测试模式: local
项目名称: (留空 - 所有项目)
难度过滤: all
并行测试: true
并行线程: 4
超时时间: 180 分钟
```

### 使用不同 LLM

**OpenAI GPT-4o:**
```yaml
LLM 提供商: openai
LLM 模型: gpt-4o
温度: 0.0
```

**Anthropic Claude:**
```yaml
LLM 提供商: anthropic
LLM 模型: claude-3-5-sonnet-20241022
温度: 0.0
```

## 📊 查看测试摘要

测试完成后，工作流页面会自动显示摘要，包括：
- ✅ 测试配置信息
- ✅ 使用的 LLM 模型
- ✅ 测试结果统计
- ✅ 生成的 Artifacts 列表

## 🔍 常见问题

### ❓ API Key 错误

**症状**：工作流失败，提示 "GEMINI_API_KEY 未配置"

**解决**：
1. 检查 Secret Name 是否拼写正确
2. 确认 API Key 有效且未过期
3. 验证选择的 LLM 提供商与配置的 Secret 匹配

### ❓ 测试超时

**症状**：工作流显示 "The operation was canceled"

**解决**：
1. 增加 `timeout_minutes` 参数（默认 120）
2. 选择难度更低的项目测试
3. 启用并行测试减少总时间

### ❓ 找不到测试报告

**症状**：Artifacts 部分为空

**解决**：
1. 确认 `upload_reports` 设置为 `true`
2. 检查测试是否成功运行完成
3. 查看日志确认报告生成步骤是否执行

### ❓ 配额不足

**症状**：提示 "Minutes quota exceeded"

**解决**：
- 公开仓库：无此限制
- 私有仓库：等待下个月配额刷新或升级计划

## 🎯 下一步

成功运行第一次测试后，你可以：

1. **调整参数**：尝试不同的 LLM 模型和温度设置
2. **测试特定项目**：使用项目名称过滤功能
3. **并行执行**：启用并行模式加速测试
4. **查看详细日志**：下载 Artifacts 深入分析

## 📚 更多资源

- 📖 [详细工作流文档](WORKFLOWS_USAGE.md)
- 📖 [.github 目录说明](README.md)
- 📖 [项目主 README](../README.md)

---

遇到问题？查看 [故障排查指南](README.md#故障排查) 或提交 Issue。
