# 压缩日志记录改进总结

## 改进内容

### 问题描述
原有的压缩日志记录只在步骤级别显示布尔标志 `compressed: true/false` 和最终的 `compressed_history` 文本，缺少以下信息：
- 压缩触发的具体时机（第几次迭代）
- 压缩的详细统计信息（命令数、token数、压缩比）
- 多次压缩的完整历史轨迹

### 解决方案

新增 `CompressionEvent` 数据结构，记录每次压缩事件的详细信息，并在 `StepContext` 中维护压缩事件列表。

## 代码修改

### 1. 数据模型层 (`src/auto_deployer/orchestrator/models.py`)

**新增 `CompressionEvent` 数据类**
```python
@dataclass
class CompressionEvent:
    """压缩事件记录"""
    iteration: int                          # 触发压缩时的迭代次数
    commands_before: int                    # 压缩前的命令总数
    commands_compressed: int                # 被压缩的命令数
    commands_kept: int                      # 保留的最近命令数
    compressed_text_length: int             # 压缩后文本的字符长度
    token_count_before: Optional[int]       # 压缩前的token估算
    token_count_after: Optional[int]        # 压缩后的token估算
    compression_ratio: float                # 压缩比率（节省的百分比）
    timestamp: str                          # 压缩时间戳
    trigger_reason: str                     # 触发原因
```

**修改 `StepContext` 类**
```python
# 新增字段
compression_events: List[CompressionEvent] = field(default_factory=list)
```

### 2. 步骤执行层 (`src/auto_deployer/orchestrator/step_executor.py`)

**增强 `_compress_step_history` 方法**
- 在压缩前后计算token数量
- 创建 `CompressionEvent` 对象记录详细信息
- 添加到 `step_ctx.compression_events` 列表
- 输出更详细的日志信息

**优化日志输出**
```
✓ History compressed at iteration 8:
   Commands: 15 total → 10 compressed + 5 kept
   Tokens: 4532 → 1823 (59.8% saved)
   Compressed text: 847 chars
```

### 3. 日志记录层 (`src/auto_deployer/orchestrator/orchestrator.py`)

**修改 `_log_step_result` 方法**
```python
# 添加压缩事件记录
compression_events_log = []
for event in step_ctx.compression_events:
    compression_events_log.append(event.to_dict())
step_log["compression_events"] = compression_events_log
```

## 日志格式示例

### 单次压缩
```json
{
  "step_id": 4,
  "step_name": "Start Gunicorn server",
  "iterations": 13,
  "compressed": true,
  "compressed_history": "...",
  "compression_events": [
    {
      "iteration": 8,
      "commands_before": 15,
      "commands_compressed": 10,
      "commands_kept": 5,
      "compressed_text_length": 847,
      "token_count_before": 4532,
      "token_count_after": 1823,
      "compression_ratio": 59.8,
      "timestamp": "2025-12-20T19:38:45.123456",
      "trigger_reason": "Token threshold 50% reached (4532/8000 tokens)"
    }
  ]
}
```

### 多次压缩
```json
{
  "compression_events": [
    {
      "iteration": 8,
      "commands_before": 15,
      "commands_compressed": 10,
      "commands_kept": 5,
      "token_count_before": 4532,
      "token_count_after": 1823,
      "compression_ratio": 59.8,
      "timestamp": "2025-12-20T19:38:45.123456"
    },
    {
      "iteration": 12,
      "commands_before": 18,
      "commands_compressed": 13,
      "commands_kept": 5,
      "token_count_before": 5621,
      "token_count_after": 2134,
      "compression_ratio": 62.0,
      "timestamp": "2025-12-20T19:40:23.654321"
    }
  ]
}
```

## 改进效果

1. **完整的压缩轨迹**：可以看到每次压缩的具体时机和效果
2. **详细的统计信息**：命令数、token数、压缩比一目了然
3. **多次压缩支持**：如果一个步骤中多次触发压缩，都会被记录
4. **便于分析调试**：可以分析压缩效果，优化压缩策略

## 测试验证

运行 `test_compression_events.py` 测试所有功能：
- ✅ CompressionEvent 数据类创建和序列化
- ✅ StepContext.compression_events 列表管理
- ✅ JSON 序列化和反序列化

## 向后兼容性

- 保留了原有的 `compressed` 和 `compressed_history` 字段
- 新增的 `compression_events` 字段为可选，不影响旧日志
- 如果没有压缩事件，`compression_events` 为空列表
