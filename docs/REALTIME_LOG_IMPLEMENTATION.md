# 实时日志写入功能实施报告

## 问题描述

之前的日志系统只在步骤结束后才将命令历史批量写入日志文件，导致：

- 在部署过程中查看日志文件，看不到正在执行的命令
- 如果步骤中途失败或程序崩溃，已执行的命令不会被记录
- 日志文件更新与控制台输出不同步

## 解决方案

实现了**实时日志同步机制**，在每条命令执行后立即更新日志文件。

### 核心修改

#### 1. 添加当前步骤上下文追踪

**文件**: `src/auto_deployer/orchestrator/orchestrator.py`

在 `DeploymentOrchestrator` 类中添加了 `current_step_ctx` 属性，用于追踪当前正在执行的步骤上下文。

```python
self.current_step_ctx: Optional[StepContext] = None  # 追踪当前执行的步骤上下文
```

#### 2. 创建实时同步方法

**文件**: `src/auto_deployer/orchestrator/orchestrator.py`

新增 `_sync_and_save_log()` 方法，在保存日志前先同步当前步骤的最新状态：

```python
def _sync_and_save_log(self) -> None:
    """同步当前步骤的命令历史到日志，然后保存"""
    if not self.current_step_ctx or not self.deployment_log.get("steps"):
        self._save_log()
        return

    # 获取当前步骤的日志条目
    step_log = self.deployment_log["steps"][-1]

    # 实时同步命令列表
    commands_log = []
    for cmd in self.current_step_ctx.commands:
        commands_log.append({
            "command": cmd.command,
            "success": cmd.success,
            "exit_code": cmd.exit_code,
            "stdout": cmd.stdout[:1000],
            "stderr": cmd.stderr[:500],
            "timestamp": cmd.timestamp,
        })
    step_log["commands"] = commands_log

    # 同步迭代计数、压缩状态、用户交互等
    step_log["iterations"] = self.current_step_ctx.iteration
    step_log["compressed"] = self.current_step_ctx.compressed_history is not None
    step_log["compressed_history"] = self.current_step_ctx.compressed_history
    # ... 其他字段同步

    # 保存到文件
    self._save_log()
```

#### 3. 更新回调机制

**文件**: `src/auto_deployer/orchestrator/orchestrator.py`

将 `StepExecutor` 的回调从 `_save_log()` 改为 `_sync_and_save_log()`：

```python
self.step_executor = StepExecutor(
    # ...
    on_command_executed=lambda: self._sync_and_save_log(),  # 使用新的同步方法
)
```

#### 4. 在步骤执行时设置上下文

**文件**: `src/auto_deployer/orchestrator/orchestrator.py`

在执行步骤前设置 `current_step_ctx`，执行后清除：

```python
# 设置当前步骤上下文，用于实时日志同步
self.current_step_ctx = step_ctx

# 执行步骤
result = self.step_executor.execute(step_ctx, deploy_ctx)

# 清除当前步骤上下文
self.current_step_ctx = None
```

## 技术细节

### 数据流

```
命令执行 (StepExecutor)
    ↓
添加到 step_ctx.commands
    ↓
触发 on_command_executed 回调
    ↓
调用 orchestrator._sync_and_save_log()
    ↓
从 current_step_ctx.commands 读取
    ↓
更新 deployment_log["steps"][-1]["commands"]
    ↓
json.dump() 写入文件
```

### 同步的内容

每次命令执行后，以下内容会立即同步到日志文件：

- ✅ 命令列表 (`commands`)
- ✅ 当前迭代次数 (`iterations`)
- ✅ 压缩状态 (`compressed`, `compressed_history`)
- ✅ 压缩事件 (`compression_events`)
- ✅ 用户交互记录 (`user_interactions`)

### 性能考虑

- **写入频率**: 每次命令执行后写入一次
- **写入方式**: 完整覆盖写入 (使用 `json.dump()`)
- **影响**: 对于正常的部署流程（每个步骤 5-10 条命令），性能影响可忽略不计
- **优化**: 如果需要，可以考虑使用文件锁或异步写入，但当前实现已足够

## 验证方法

### 方法 1：使用测试脚本

运行 `test_realtime_log.py` 监控日志文件变化：

```bash
python test_realtime_log.py
```

在另一个终端运行部署：

```bash
auto-deployer deploy --repo <repo-url> --local
```

测试脚本会实时显示日志文件的更新。

### 方法 2：手动验证

1. 启动一个部署：

   ```bash
   auto-deployer deploy --repo git@github.com:ctfy66/Auto-Deployer-sample-repo.git --local
   ```

2. 在部署过程中，打开日志文件：

   ```bash
   # 查找最新日志
   Get-ChildItem agent_logs | Sort-Object LastWriteTime -Descending | Select-Object -First 1

   # 实时查看
   Get-Content agent_logs\deploy_xxx.json -Wait
   ```

3. 观察：
   - ✅ 命令执行后，日志文件立即包含该命令
   - ✅ 不需要等到步骤结束
   - ✅ 即使中途中断，已执行的命令也会被保存

### 方法 3：检查时间戳

查看日志文件中的时间戳：

```json
{
  "commands": [
    {
      "command": "...",
      "timestamp": "2025-12-20T22:06:37.842219" // 命令执行时间
    },
    {
      "command": "...",
      "timestamp": "2025-12-20T22:07:08.564333" // 下一条命令
    }
  ],
  "timestamp": "2025-12-20T22:07:12.218645" // 步骤完成时间
}
```

每条命令的 `timestamp` 应该与其实际执行时间一致。

## 影响范围

### 修改的文件

- `src/auto_deployer/orchestrator/orchestrator.py` (新增 1 个方法，修改 4 处)

### 不影响

- ✅ 日志文件格式保持不变
- ✅ 向后兼容现有日志
- ✅ 不影响 `StepExecutor` 的执行逻辑
- ✅ 不影响 `_log_step_result()` 的最终更新

### 受益

- ✅ 实时查看部署进度
- ✅ 更好的调试体验
- ✅ 即使程序崩溃也能看到执行历史
- ✅ 日志文件与控制台输出完全同步

## 总结

通过引入 `current_step_ctx` 和 `_sync_and_save_log()` 机制，我们实现了日志文件的实时同步，解决了原有的延迟写入问题。这个改动是最小侵入式的，不影响现有功能，同时显著提升了用户体验。

---

**实施日期**: 2025-12-20
**实施者**: Auto-Deployer Team
