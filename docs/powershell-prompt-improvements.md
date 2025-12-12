# PowerShell 提示词改进说明

## 改进日期
2025-12-12

## 改进背景

在部署日志 `deploy_Auto-Deployer-sample-repo_20251212_231013.json` 中发现agent在Windows环境下重复遇到PowerShell语法错误，主要问题：

1. **反复使用 `&&` 操作符**：导致"标记'&&'不是此版本中的有效语句分隔符"错误
2. **命令链接过度**：尝试在一个命令中完成多个操作
3. **虚拟环境激活失败**：未能正确处理PowerShell执行策略和路径问题
4. **误判成功状态**：虽然pip install成功但实际安装到系统Python而非虚拟环境

## 主要改进内容

### 1. 强制单命令执行策略

**文件**: `src/auto_deployer/prompts/execution_step.py`

#### Windows平台 (强制)
```
🔥 ONE COMMAND PER ACTION (CRITICAL)
- 执行ONLY ONE atomic command per action
- Do NOT chain commands with &&, ||, or multiple ;
- 如果需要运行多个命令，拆分为多个独立的actions
```

**示例**:
```json
// 错误 ❌
{"action": "execute", "command": "cd dir && python -m venv venv"}

// 正确 ✅
{"action": "execute", "command": "cd dir"}
// 然后下一个action:
{"action": "execute", "command": "python -m venv venv"}
```

#### Linux/macOS平台 (建议)
```
PREFER ONE COMMAND PER ACTION (BEST PRACTICE)
- 优先执行ONE atomic command per action
- 虽然 && 可用，但分离的actions更可靠
- 如果必须链接，最多2-3个相关命令
```

### 2. PowerShell语法常识库

新增 **Windows PowerShell Syntax Rules** 部分，包含：

#### 命令链接规则
```markdown
FORBIDDEN (禁止使用):
- ❌ && - NOT supported in PowerShell 5.x
- ❌ || - NOT supported in PowerShell 5.x

ALLOWED (允许使用):
- ✅ ONE COMMAND PER ACTION (最佳实践)
- ✅ Semicolon ; (谨慎使用)
- ✅ Pipeline | (传递输出)
```

#### PowerShell路径语法
```powershell
- 使用反斜杠: C:\\Users\\DELL\\project
- 或正斜杠: C:/Users/DELL/project (PowerShell自动转换)
- 带空格路径加引号: "C:\\Program Files\\App"
- 家目录: $env:USERPROFILE (不是 ~)
```

#### 常用PowerShell命令速查表
```powershell
- 克隆: git clone <repo> "C:\\Users\\DELL\\app"
- 删除文件夹: Remove-Item -Recurse -Force <path>
- 创建目录: New-Item -ItemType Directory -Path <path>
- 测试路径: Test-Path <path>
- 列出目录: Get-ChildItem <path>
- 后台进程: Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "start"
- 检查进程: Get-Process -Name node -ErrorAction SilentlyContinue
- 检查服务: Get-Service -Name Docker
- 查找端口: netstat -ano | findstr :<port>
- 杀死进程: Stop-Process -Id <pid> -Force
```

### 3. 虚拟环境激活最佳实践

#### 识别常见问题
```
错误: ".\\venv\\Scripts\\Activate.ps1"项识别为 cmdlet、函数、脚本文件或可运行程序的名称
根本原因: 执行策略或路径问题
```

#### 解决方案模式
```json
// 步骤1: 设置执行策略
{"action": "execute", "command": "Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force"}

// 步骤2: 尝试激活 (可能仍会失败)
{"action": "execute", "command": "cd C:\\project; .\\venv\\Scripts\\Activate.ps1"}

// 步骤3: 如果激活失败，直接使用venv的pip
{"action": "execute", "command": ".\\venv\\Scripts\\pip.exe install -r requirements.txt"}

// 步骤4: 直接使用venv的python运行应用
{"action": "execute", "command": ".\\venv\\Scripts\\python.exe app.py"}
```

#### 关键洞察
```
你不总是需要"激活"虚拟环境。直接使用venv的python/pip：
- venv\\Scripts\\python.exe 代替 python
- venv\\Scripts\\pip.exe 代替 pip
```

### 4. 规则清单增强

新的强制规则（Windows）：

1. **ONE COMMAND PER ACTION (CRITICAL)** - 每个action只执行一个原子命令
2. **PowerShell Syntax** - 使用PowerShell语法，不是bash
3. **Virtual Environment Handling** - 虚拟环境处理建议
4. **Chain of Thought Reasoning** - CoT推理是强制性的
5. **Iteration Limits** - 迭代次数限制和求助时机
6. **Error Handling** - 错误分析而不是盲目重试
7. **Success Verification** - 成功验证不能仅依赖exit code
8. **Asking for Help** - 3次失败后应该求助用户

### 5. Available Actions提示增强

在action定义部分添加了醒目的警告：

```json
1. Execute a PowerShell command (⚠️ ONE COMMAND ONLY - NO CHAINING):
{
  "action": "execute",
  "command": "single atomic PowerShell command (NO && or ||)",
  ...
}

⚠️ CRITICAL: Each "execute" action must contain ONLY ONE atomic command.
If you need to run multiple commands, create multiple sequential actions.
DO NOT use && to chain commands - it will fail in PowerShell 5.x.
```

## 预期效果

这些改进应该能够：

1. ✅ **消除PowerShell语法错误** - agent将知道不能使用 `&&`
2. ✅ **提高执行成功率** - 每次执行单个命令，更容易调试
3. ✅ **正确处理虚拟环境** - 知道可以直接使用venv的python/pip
4. ✅ **减少迭代次数** - 避免重复相同的失败尝试
5. ✅ **更好的错误恢复** - 清晰的解决方案模式

## 测试建议

使用相同的测试仓库重新部署：

```bash
auto-deployer deploy --repo https://github.com/ctfy66/Auto-Deployer-sample-repo --local
```

预期结果：
- Step 3应该在更少的迭代次数内完成（目标：< 5次迭代，之前：13次）
- 不应出现 "标记'&&'不是此版本中的有效语句分隔符" 错误
- 虚拟环境应该正确创建并使用
- 依赖应该安装到虚拟环境中而不是系统Python

## 相关文件

- `src/auto_deployer/prompts/execution_step.py` - 主要修改文件
- `docs/chain-of-thought-implementation.md` - CoT框架文档
- `agent_logs/deploy_Auto-Deployer-sample-repo_20251212_231013.json` - 原始问题日志

## 后续改进方向

1. **添加PowerShell版本检测** - 在probing阶段检测PowerShell版本，针对性调整策略
2. **增强venv验证** - 在创建venv后验证Scripts目录存在
3. **pip安装路径验证** - 安装后检查pip list输出的路径确认在venv中
4. **执行策略自动设置** - 在部署开始时预设执行策略避免后续问题

