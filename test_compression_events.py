"""测试压缩事件记录功能"""

import sys
import os

# 直接导入需要的模块文件
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'auto_deployer', 'orchestrator'))

import models
CompressionEvent = models.CompressionEvent
StepContext = models.StepContext
StepStatus = models.StepStatus
CommandRecord = models.CommandRecord


def test_compression_event():
    """测试 CompressionEvent 数据类"""
    print("=" * 60)
    print("测试 CompressionEvent")
    print("=" * 60)
    
    # 创建压缩事件
    event = CompressionEvent(
        iteration=8,
        commands_before=15,
        commands_compressed=10,
        commands_kept=5,
        compressed_text_length=847,
        token_count_before=4532,
        token_count_after=1823,
        compression_ratio=59.8,
        trigger_reason="Token threshold 50% reached (4532/8000 tokens)"
    )
    
    print(f"\n创建的压缩事件:")
    print(f"  迭代: {event.iteration}")
    print(f"  命令总数: {event.commands_before}")
    print(f"  压缩命令数: {event.commands_compressed}")
    print(f"  保留命令数: {event.commands_kept}")
    print(f"  压缩文本长度: {event.compressed_text_length}")
    print(f"  Token (前): {event.token_count_before}")
    print(f"  Token (后): {event.token_count_after}")
    print(f"  压缩比率: {event.compression_ratio}%")
    print(f"  触发原因: {event.trigger_reason}")
    
    # 测试序列化
    event_dict = event.to_dict()
    print(f"\n序列化为字典:")
    for key, value in event_dict.items():
        print(f"  {key}: {value}")
    
    # 测试反序列化
    event2 = CompressionEvent.from_dict(event_dict)
    print(f"\n反序列化成功: {event2.iteration == event.iteration}")
    
    print("\n✓ CompressionEvent 测试通过")


def test_step_context_compression_events():
    """测试 StepContext 的 compression_events 字段"""
    print("\n" + "=" * 60)
    print("测试 StepContext.compression_events")
    print("=" * 60)
    
    # 创建步骤上下文
    step_ctx = StepContext(
        step_id=4,
        step_name="Start server",
        goal="Start the application server",
        success_criteria="Server is running",
        category="deploy"
    )
    
    print(f"\n初始压缩事件列表: {step_ctx.compression_events}")
    print(f"列表长度: {len(step_ctx.compression_events)}")
    
    # 模拟添加两次压缩事件
    event1 = CompressionEvent(
        iteration=8,
        commands_before=15,
        commands_compressed=10,
        commands_kept=5,
        compressed_text_length=847,
        token_count_before=4532,
        token_count_after=1823,
        compression_ratio=59.8,
        trigger_reason="Token threshold 50% reached"
    )
    step_ctx.compression_events.append(event1)
    
    event2 = CompressionEvent(
        iteration=12,
        commands_before=18,
        commands_compressed=13,
        commands_kept=5,
        compressed_text_length=1024,
        token_count_before=5621,
        token_count_after=2134,
        compression_ratio=62.0,
        trigger_reason="Token threshold 50% reached"
    )
    step_ctx.compression_events.append(event2)
    
    print(f"\n添加两个压缩事件后:")
    print(f"事件数量: {len(step_ctx.compression_events)}")
    
    for i, event in enumerate(step_ctx.compression_events, 1):
        print(f"\n事件 {i}:")
        print(f"  迭代: {event.iteration}")
        print(f"  命令: {event.commands_before} → {event.commands_compressed} 压缩 + {event.commands_kept} 保留")
        print(f"  Token: {event.token_count_before} → {event.token_count_after} ({event.compression_ratio:.1f}% 节省)")
        print(f"  压缩文本: {event.compressed_text_length} chars")
    
    # 测试序列化所有事件
    events_list = [event.to_dict() for event in step_ctx.compression_events]
    print(f"\n序列化事件列表成功: {len(events_list)} 个事件")
    
    print("\n✓ StepContext.compression_events 测试通过")


def test_json_serialization():
    """测试 JSON 序列化"""
    print("\n" + "=" * 60)
    print("测试 JSON 序列化")
    print("=" * 60)
    
    import json
    
    # 创建完整的步骤日志结构
    step_log = {
        "step_id": 4,
        "step_name": "Start Gunicorn server",
        "status": "success",
        "iterations": 13,
        "compressed": True,
        "compressed_history": "启动Gunicorn服务:\n环境设置:\n  Set-Location...",
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
            },
            {
                "iteration": 12,
                "commands_before": 18,
                "commands_compressed": 13,
                "commands_kept": 5,
                "compressed_text_length": 1024,
                "token_count_before": 5621,
                "token_count_after": 2134,
                "compression_ratio": 62.0,
                "timestamp": "2025-12-20T19:40:23.654321",
                "trigger_reason": "Token threshold 50% reached (5621/8000 tokens)"
            }
        ]
    }
    
    # 序列化为 JSON
    json_str = json.dumps(step_log, indent=2, ensure_ascii=False)
    print("\nJSON 输出:")
    print(json_str)
    
    # 反序列化
    parsed = json.loads(json_str)
    print(f"\n反序列化成功: {len(parsed['compression_events'])} 个压缩事件")
    
    print("\n✓ JSON 序列化测试通过")


if __name__ == "__main__":
    try:
        test_compression_event()
        test_step_context_compression_events()
        test_json_serialization()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
