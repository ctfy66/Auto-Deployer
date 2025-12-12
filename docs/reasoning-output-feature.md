# Reasoning 和 Extracted Output 功能

## 概述

此功能增强了 Auto-Deployer 的日志记录和输出，使得：
1. **模型的推理过程（reasoning）** 能够在终端输出和日志文件中可见
2. **提取后的命令输出** 除了发送给 LLM，也会记录到日志文件中

这样可以更好地理解 LLM 的决策过程，同时保留完整的输出信息用于调试。

## 功能特性

### 1. Reasoning 输出

**终端显示**：
```
🔧 [1] git clone https://github.com/user/repo /app
💭 Reason: 需要克隆仓库到指定目录以开始部署
```

**日志记录** (`agent_logs/*.json`):
```json
{
  "commands": [
    {
      "command": "git clone https://github.com/user/repo /app",
      "reasoning": "需要克隆仓库到指定目录以开始部署",
      "success": true,
      "exit_code": 0,
      ...
    }
  ]
}
```

### 2. Extracted Output 记录

**终端显示**：
```
============================================================
📤 LLM将看到的提取后输出:
------------------------------------------------------------
✓ Command succeeded: git clone... | path: /app
Key Info:
  - path: /app
[Compressed: 2547→157 chars, 93.8% saved]
============================================================
```

**日志记录**：
```json
{
  "commands": [
    {
      "command": "git clone https://github.com/user/repo /app",
      "extracted_output": "✓ Command succeeded: git clone... | path: /app\nKey Info:\n  - path: /app\n[Compressed: 2547→157 chars, 93.8% saved]",
      "stdout": "Cloning into '/app'...\nremote: Enumerating objects: 100...",
      "stderr": ""
    }
  ]
}
```

### 3. 保留原始输出

日志文件同时保留：
- `extracted_output`: 提取后的输出（发送给 LLM 的版本）
- `stdout`: 原始标准输出（截断至 2000 字符）
- `stderr`: 原始错误输出（截断至 2000 字符）

## 实现细节

### 修改的文件

1. **`src/auto_deployer/orchestrator/step_executor.py`**
   - 将 reasoning 日志级别从 DEBUG 提升到 INFO
   - 修改 `_execute_command` 方法接受 reasoning 参数
   - 在 CommandRecord 中添加临时属性存储额外信息
   - 添加终端输出显示提取后的输出

2. **`src/auto_deployer/orchestrator/orchestrator.py`**
   - 修改 `_log_step_result` 方法记录 reasoning 和 extracted_output
   - 使用 `getattr` 安全获取临时属性

3. **`src/auto_deployer/llm/agent.py`** (Legacy Agent)
   - 在 `deploy()` 和 `deploy_local()` 方法中添加类似的修改
   - 确保 reasoning 和 extracted_output 都被记录

### 日志结构变化

**Orchestrator 模式**：
```json
{
  "version": "2.0",
  "mode": "orchestrator",
  "steps": [
    {
      "step_id": 1,
      "step_name": "Clone repository",
      "commands": [
        {
          "command": "git clone ...",
          "reasoning": "需要克隆仓库...",          // 新增 ✅
          "extracted_output": "✓ Command...",     // 新增 ✅
          "stdout": "Cloning into...",             // 原始输出
          "stderr": "",
          "success": true,
          "exit_code": 0
        }
      ]
    }
  ]
}
```

**Legacy Agent 模式**：
```json
{
  "steps": [
    {
      "iteration": 1,
      "action": "execute",
      "command": "git clone ...",
      "reasoning": "需要克隆仓库...",
      "result": {
        "success": true,
        "exit_code": 0,
        "extracted_output": "✓ Command...",      // 新增 ✅
        "stdout": "Cloning into...",
        "stderr": "",
        "extracted_summary": "✓ Command succeeded..."
      }
    }
  ]
}
```

## 使用示例

### 运行部署

```bash
# 设置 API key
$env:AUTO_DEPLOYER_DEEPSEEK_API_KEY = "your-key"

# 运行本地部署
auto-deployer deploy --repo https://github.com/user/repo --local
```

### 查看终端输出

部署过程中会看到：
```
📍 Step 1/5: Clone repository (Iteration 1)
   🔧 [1] git clone https://github.com/user/repo /app
   💭 Reason: 需要克隆仓库到指定目录以开始部署
   
============================================================
📤 LLM将看到的提取后输出:
------------------------------------------------------------
✓ Command succeeded: git clone... | path: /app
Key Info:
  - path: /app
[Compressed: 2547→157 chars, 93.8% saved]
============================================================

      ✓ Exit code: 0
```

### 查看日志文件

```bash
# 列出所有日志
auto-deployer logs --list

# 查看最新日志
auto-deployer logs --latest

# 或直接打开 JSON 文件
cat agent_logs/deploy_repo_20241212_123456.json
```

在日志文件中搜索：
- `"reasoning"`: 查看所有 LLM 的推理过程
- `"extracted_output"`: 查看发送给 LLM 的提取后输出
- `"stdout"`: 查看原始命令输出

## 测试验证

运行测试脚本验证功能：
```bash
python test_log_structure.py
```

测试会验证：
1. 日志结构是否包含新字段
2. JSON 序列化是否正常
3. 实际日志文件是否包含新字段（如果已运行过部署）

## 好处

### 1. 更好的可观察性
- 可以看到 LLM 为什么做出某个决策
- 有助于理解自动化部署的逻辑

### 2. 调试更容易
- 原始输出和提取后输出都被保存
- 可以验证输出提取器是否正确工作
- 可以重现 LLM 看到的内容

### 3. 审计和分析
- 完整的推理过程记录便于事后分析
- 可以用于改进提示词和策略
- 有助于识别常见问题模式

## 注意事项

1. **日志文件大小**: 虽然提取器会压缩输出，但保留原始输出会增加日志文件大小。原始输出被截断至 2000 字符以控制大小。

2. **隐私**: reasoning 和命令输出可能包含敏感信息（路径、配置等），请注意保护日志文件。

3. **向后兼容**: 旧版本生成的日志文件不包含这些新字段，但不影响读取。

## 相关文档

- [Output Extractor](../src/auto_deployer/llm/output_extractor.py) - 智能输出提取器
- [Step Executor](../src/auto_deployer/orchestrator/step_executor.py) - 步骤执行器
- [Deployment Agent](../src/auto_deployer/llm/agent.py) - Legacy Agent

## 更新日志

- **2024-12-12**: 初始实现
  - 添加 reasoning 终端输出和日志记录
  - 添加 extracted_output 日志记录
  - 保留原始输出用于调试

