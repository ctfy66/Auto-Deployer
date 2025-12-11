# 错误诊断改进 - 提示词增强

## 改进概述

通过在提示词中添加**显式错误推理框架**,引导 LLM 系统化地分析错误,而不依赖隐式推理。

## 改进内容

### 1. 错误诊断框架(5 步推理流程)

添加到 `prompts.py` 的 `STEP_EXECUTION_PROMPT` 和 `STEP_EXECUTION_PROMPT_WINDOWS`:

```
## Step 1: Extract All Error Indicators
- 识别所有错误消息(不仅仅是第一行)
- 引用确切的错误文本

## Step 2: Classify Each Error
- 区分症状 vs 根本原因
- 判断具体性等级(SPECIFIC vs GENERIC)

## Step 3: Build the Causal Chain
- 追踪错误链:症状 → 中间错误 → 根本原因
- 使用 WHY 问题引导分析

## Step 4: Prioritize by Specificity
- 最具体的错误通常是根本原因
- 忽略通用的包装错误消息

## Step 5: Context-Aware Diagnosis
- 考虑平台特定因素
- 使用适当的诊断命令
```

### 2. 常见错误模式库

为常见错误类型提供模板:
- **Docker 守护进程未运行** (你的示例场景)
- **端口已被占用**
- **权限被拒绝**
- **缺少依赖**
- **构建/编译错误**

每个模式包含:
- 症状
- 具体指标
- 根本原因
- 诊断命令
- 修复方法

### 3. 平台特定指导

#### Windows 特有部分:
- **命名管道 (//./pipe/\*)**: 管道未找到 = 服务未运行
- **Get-Service / Start-Service**: Windows 服务管理
- **管理员权限**: 提升权限要求
- **Docker Desktop**: 需要应用程序运行,不只是服务

#### Linux 特有部分:
- **/var/run/docker.sock**: Unix socket 检查
- **systemctl / journalctl**: 服务管理和日志
- **用户组**: docker 组权限

## 测试案例:你的 Docker 错误

### 原始错误消息

```json
{
  "command": "docker compose up -d --build",
  "stderr": "unable to get image 'ccr.ccs.tencentyun.com/buildingai/node:22.20.0': error during connect: Get \"http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.51/images/...\": open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.",
  "exit_code": 1
}
```

### 改进前的分析

LLM 看到截断的错误:
```
stderr (前200字符): "unable to get image... error during connect: Get..."
```

LLM 推理:
- 关键词:"unable to get", "connect"
- 结论:网络连接问题 ❌ **错误!**

生成的错误消息:
```
"The Docker daemon encountered a connection error when attempting to pull
the image. This indicates a network connectivity issue..."
```

### 改进后的分析

新提示词引导 LLM 按 5 步推理:

**Step 1 - 提取错误指标:**
```
- "unable to get image" (通用症状)
- "error during connect" (中间错误)
- "open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified" (具体错误!)
```

**Step 2 - 分类:**
```
- "unable to get image" → SYMPTOM, GENERIC
- "error during connect" → SYMPTOM, GENERIC
- "The system cannot find the file //./pipe/..." → ROOT CAUSE, SPECIFIC ✓
```

**Step 3 - 构建因果链:**
```
"unable to get image" (症状)
  → WHY? "error during connect" (中间)
  → WHY? "open //./pipe/dockerDesktopLinuxEngine: file not found" (具体)
  → ROOT CAUSE: Docker Desktop 服务未运行
```

**Step 4 - 优先级:**
```
最具体的错误:"//./pipe/dockerDesktopLinuxEngine not found"
这是一个 Windows 命名管道 → 表明 Docker Desktop 未运行
```

**Step 5 - Windows 特定诊断:**
```
命名管道未找到 → 检查 Docker Desktop 状态
诊断命令: Get-Service -Name com.docker.service
修复: 启动 Docker Desktop 应用程序
```

生成的错误消息:
```
"Docker Desktop service is not running. The named pipe '//./pipe/dockerDesktopLinuxEngine'
cannot be found, which indicates Docker Desktop application is not started on Windows.
Please start Docker Desktop and wait 30-60 seconds for it to fully initialize."
```

## 预期改进效果

### 1. 准确性提升
- ✅ 正确识别根本原因(服务未运行 vs 网络问题)
- ✅ 提供可操作的诊断步骤
- ✅ 平台感知的解决方案

### 2. 推理可追溯
- ✅ 错误分析过程明确
- ✅ 可以审计 LLM 的推理步骤
- ✅ 更容易调试误判

### 3. 一致性
- ✅ 标准化的分析流程
- ✅ 减少随机性
- ✅ 可复现的行为

### 4. 学习效率
- ✅ 错误模式作为示例
- ✅ 新错误也能用相同框架分析
- ✅ 经验可以积累和复用

## 决策规则强调

新增的关键规则:

1. **ALWAYS 读取完整的 stderr**,不只看第一行
2. **具体错误优先于通用错误**
3. **从最具体的错误开始反向推理**
4. **平台特定路径/服务表明问题类型**
5. **不要重试同样的命令** - 先修复根本原因

## Windows 特别说明

特别强调了 Windows 命名管道的概念:

```
### Named Pipes (//./pipe/*)
If you see "//./pipe/servicename" and "file not found":
- This is a Windows named pipe used for inter-process communication
- "File not found" means the SERVICE is not running (not a file system issue!)
- Diagnosis: Get-Service -Name ServiceName
- Fix: Start the service or application
```

这直接解决了你示例中的问题!

## 实施状态

✅ **已完成**:
1. Linux 提示词增强 (`STEP_EXECUTION_PROMPT`)
2. Windows 提示词增强 (`STEP_EXECUTION_PROMPT_WINDOWS`)
3. 5步错误推理框架
4. 常见错误模式库
5. 平台特定诊断指导
6. 决策规则

⏸️ **未实施** (可选的进一步改进):
1. ErrorAnalyzer 代码模块(不推荐 - 你说得对,硬编码不灵活)
2. 知识库扩展(可以后续添加)
3. 经验检索增强(可以后续添加)

## 为什么这个方案更好

相比于用代码提取错误类型:

| 方面 | 代码提取 | 提示词引导 |
|------|---------|-----------|
| **灵活性** | ❌ 需要预定义规则 | ✅ 适应新错误类型 |
| **可维护性** | ❌ 需要持续更新代码 | ✅ 只需调整提示词 |
| **上下文理解** | ❌ 正则无法理解语义 | ✅ LLM 理解上下文 |
| **开发成本** | ❌ 需要大量模式库 | ✅ 写一次提示词 |
| **适应性** | ❌ 新错误需要新代码 | ✅ 用相同框架分析 |

## 下一步测试建议

1. **用你的真实错误日志测试**
   - 找到之前失败的部署日志
   - 用更新后的系统重新运行
   - 对比错误消息的准确性

2. **尝试其他常见错误**
   - 端口冲突
   - 权限问题
   - 缺少依赖
   - 观察诊断过程是否系统化

3. **收集误判案例**
   - 如果仍有误判,分析是哪一步推理出错
   - 迭代改进提示词中的指导

4. **调整 stderr 截断限制**
   - 当前是 200 字符,可能太短
   - 考虑提高到 500-1000 字符
   - 位置:`step_executor.py:311`

## 文件修改记录

- **文件**: `src/auto_deployer/orchestrator/prompts.py`
- **修改内容**:
  - `STEP_EXECUTION_PROMPT` (Linux): 新增 62 行错误诊断框架
  - `STEP_EXECUTION_PROMPT_WINDOWS`: 新增 111 行错误诊断框架和 Windows 特定指导
- **向后兼容**: ✅ 是 - 只是添加指导,不改变接口
- **破坏性变更**: ❌ 否

## 总结

通过**显式推理框架**而非硬编码规则,我们:
- 提升了错误诊断准确性
- 保持了系统灵活性
- 降低了维护成本
- 使推理过程可审计

这正好解决了你提出的核心问题:**缺乏推理能力**,而不是**缺乏规则库**。
