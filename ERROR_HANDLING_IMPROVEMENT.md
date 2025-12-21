# 错误处理提示词增强

## 概述

本次更新为 `orchestrator/prompts.py` 中的步骤执行系统提示词添加了全面的错误诊断和处理指南。

## 实施日期

2025-12-21

## 修改内容

### 1. 新增函数：`_get_error_diagnosis_guide(is_windows: bool)`

创建了一个新函数来生成错误诊断指南，支持 Windows 和 Linux 平台的特定指导。

**位置**：`src/auto_deployer/orchestrator/prompts.py`，第 56 行

### 2. 错误诊断指南包含以下四个主要部分：

#### 2.1 常见错误模式 (Common Error Patterns)

涵盖 8 大类错误，共 20+ 种具体错误模式：

1. **Git 错误**：仓库已存在、仓库未找到、SSH 密钥问题
2. **文件系统错误**：文件不存在、权限拒绝、文件已存在
3. **服务连接错误**：无法连接、连接被拒绝、管道未找到
4. **端口冲突**：EADDRINUSE、地址已被使用
5. **Docker 错误**：守护进程未运行、镜像未找到、挂载错误、容器已存在
6. **依赖/包错误**：模块未找到、命令未找到、包未找到
7. **超时错误**：IDLE_TIMEOUT、TOTAL_TIMEOUT
8. **构建/编译错误**：依赖缺失、语法错误、环境变量未设置

每种错误都提供了：
- 错误特征识别
- 可能的原因
- 建议的解决方案

#### 2.2 系统化诊断步骤 (Systematic Diagnosis Steps)

提供 6 步诊断流程：

1. **读取完整错误信息** - 检查 stderr 和 stdout
2. **识别错误类型** - 匹配常见模式
3. **检查前置条件** - 服务状态、文件存在性、权限、端口
4. **收集上下文** - 进程列表、磁盘空间、日志
5. **应用修复** - 根据错误类型采取对应措施
6. **验证修复** - 重新检查条件，不要盲目重试

#### 2.3 渐进式超时处理策略 (Progressive Timeout Strategy)

**核心原则**：不使用阻塞命令（`-f`, `--follow`），使用后台执行 + 渐进式等待

**等待策略**：
- 步骤 1：启动后台进程
- 步骤 2：等待 30-60 秒，检查状态
- 步骤 3：等待 2-3 分钟，再次检查
- 步骤 4：等待 5 分钟，全面检查
- 步骤 5：总计 15 分钟后仍未就绪 → 可能失败

**平台特定命令**：
- Windows: `Start-Process -NoNewWindow`, `Start-Sleep`, `Get-Process`
- Linux: `nohup`, `sleep`, `ps aux`
- Docker: `docker compose up -d`, `docker logs --tail 50 --since 2m`

#### 2.4 何时放弃的判断标准 (When to Give Up)

**应该声明 step_failed 的情况**（5 大类）：
1. 重复失败：相同命令失败 3 次以上
2. 根本性问题：仓库不存在、工具无法安装、系统限制
3. 需要用户输入：配置决策、凭证/API 密钥（应使用 ask_user）
4. 资源耗尽：等待 15 分钟无进展、接近迭代上限（25/30）
5. 不可恢复错误：文件系统损坏、架构不兼容、依赖冲突

**不应该放弃的情况**（4 大类）：
1. 首次失败
2. 服务启动中且日志显示进展
3. 可修复的问题（权限、端口、缺失文件、目录冲突）
4. 迭代预算充足（如只用了 5/30 次）

**黄金法则**：
- 是否识别了根本原因？
- 是否尝试了适当的修复？
- 还有其他可尝试的方法吗？

只有三个问题都是 YES 才应该放弃。

### 3. 平台特定诊断

**Windows 特定**：
- Docker Desktop 检查：`Get-Process "Docker Desktop"`
- 服务管理：`Get-Service`, `Start-Service`
- 路径操作：`Test-Path`，注意反斜杠转义
- 后台进程：`Start-Process -NoNewWindow`
- 端口检查：`Get-NetTCPConnection -LocalPort`

**Linux 特定**：
- 权限：`sudo`, `chmod`, `chown`
- 服务管理：`systemctl`, `service`
- 进程检查：`ps aux`, `pgrep`
- 端口检查：`lsof -i`, `netstat -tuln`
- 后台进程：`nohup`, `&`

### 4. 集成到系统提示词

修改了 `build_step_system_prompt()` 函数：
- 在"Current Step"部分之后
- 在"Instructions"部分之前
- 插入完整的错误诊断指南

这确保 LLM 在执行每个步骤时都能看到这些指导。

## 统计信息

- **新增代码量**：约 200 行
- **新增字符数**：~7,700 字符
- **预估 token 增加**：~1,900 tokens
- **错误模式类别**：8 大类
- **具体错误模式**：20+ 种
- **诊断步骤**：6 步流程
- **等待策略**：5 步渐进式
- **放弃判断标准**：5 类应该 + 4 类不应该

## 预期效果

1. **减少重复失败命令**：LLM 能识别相同命令的重复并采取不同策略
2. **更智能的超时处理**：使用渐进式等待而不是阻塞命令
3. **更快的错误恢复**：快速匹配错误模式并应用对应修复
4. **减少浪费的迭代**：在适当时机声明失败而不是盲目重试
5. **更好的平台兼容性**：Windows 和 Linux 都有特定的诊断指导

## 真实案例改进

基于 `deploy_BuildingAI_20251221_151759.json` 日志分析的实际错误：

| 错误类型 | 原有覆盖 | 现在覆盖 |
|---------|---------|---------|
| `fatal: destination path ... already exists` | ❌ | ✅ Git 错误 #1 |
| `找不到路径 .env.example` | ❌ | ✅ 文件系统错误 #1 |
| `failed to connect to docker API pipe` | 部分 | ✅ 服务连接错误 #3 + Windows 特定 |
| `error while creating mount source path` | ❌ | ✅ Docker 错误 #3 |
| `IDLE_TIMEOUT`, `TOTAL_TIMEOUT` | ❌ | ✅ 超时错误 #7 + 渐进式策略 |
| 重复 30 次无效命令 | ❌ | ✅ 何时放弃 #1 |

## 后续建议

1. **监控效果**：在接下来的部署中观察 LLM 的错误处理行为
2. **调整阈值**：根据实际情况调整等待时间和重试次数
3. **添加更多模式**：持续收集新的错误模式并补充到指南中
4. **优化提示词长度**：如果 token 使用过高，考虑精简部分内容

## 测试验证

✅ 语法检查通过  
✅ 类型检查通过（无错误）  
✅ 内容完整性验证通过（11/11 项检查）  
✅ 8 大错误类别全部包含  
✅ Windows 和 Linux 特定指导都已添加  
✅ 成功集成到系统提示词中

## 文件修改

- **修改文件**：`src/auto_deployer/orchestrator/prompts.py`
- **新增函数**：`_get_error_diagnosis_guide()`
- **修改函数**：`build_step_system_prompt()` - 添加错误指南调用和插入
- **行数变化**：+196 行

## 兼容性

- ✅ 向后兼容：不影响现有功能
- ✅ 平台兼容：支持 Windows 和 Linux
- ✅ LLM 兼容：适用于所有 LLM 提供商
- ✅ 配置兼容：不需要修改配置文件
