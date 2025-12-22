"""测试交互配置功能"""

from auto_deployer.config import load_config, InteractionConfig
from auto_deployer.interaction import (
    AutoRetryHandler,
    AutoResponseHandler,
    CLIInteractionHandler,
    InteractionRequest,
    InputType,
    QuestionCategory,
)


def test_config_loading():
    """测试配置加载"""
    print("=" * 60)
    print("测试 1: 配置加载")
    print("=" * 60)
    
    config = load_config()
    
    print(f"✓ 交互配置已加载")
    print(f"  - enabled: {config.interaction.enabled}")
    print(f"  - mode: {config.interaction.mode}")
    print(f"  - auto_retry_on_interaction: {config.interaction.auto_retry_on_interaction}")
    print()


def test_auto_retry_handler():
    """测试 AutoRetryHandler"""
    print("=" * 60)
    print("测试 2: AutoRetryHandler")
    print("=" * 60)
    
    handler = AutoRetryHandler(retry_message="retry")
    
    # 创建一个交互请求
    request = InteractionRequest(
        question="选择应用运行端口",
        input_type=InputType.CHOICE,
        options=["3000", "8080", "5000"],
        category=QuestionCategory.DECISION,
        default="3000",
    )
    
    # 获取响应
    response = handler.ask(request)
    
    print(f"✓ AutoRetryHandler 测试")
    print(f"  - 响应值: {response.value}")
    print(f"  - 是否自定义: {response.is_custom}")
    print(f"  - 元数据: {response.metadata}")
    
    assert response.value == "retry", "应该返回 'retry'"
    assert response.is_custom is True, "应该标记为自定义输入"
    assert response.metadata and response.metadata.get("auto_retry") is True, "应该包含 auto_retry 元数据"
    
    print("✓ 所有断言通过！")
    print()


def test_auto_response_handler():
    """测试 AutoResponseHandler"""
    print("=" * 60)
    print("测试 3: AutoResponseHandler")
    print("=" * 60)
    
    handler = AutoResponseHandler(use_defaults=True, always_confirm=True)
    
    # 创建一个带默认值的请求
    request = InteractionRequest(
        question="选择应用运行端口",
        input_type=InputType.CHOICE,
        options=["3000", "8080", "5000"],
        category=QuestionCategory.DECISION,
        default="3000",
    )
    
    # 获取响应
    response = handler.ask(request)
    
    print(f"✓ AutoResponseHandler 测试")
    print(f"  - 响应值: {response.value}")
    print(f"  - 应该使用默认值: {response.value == '3000'}")
    
    assert response.value == "3000", "应该使用默认值"
    
    print("✓ 所有断言通过！")
    print()


def test_interaction_modes():
    """测试不同交互模式的配置"""
    print("=" * 60)
    print("测试 4: 交互模式配置")
    print("=" * 60)
    
    # 模拟不同的配置
    configs = [
        ("cli", True, True, "CLI交互模式"),
        ("auto", True, True, "自动重试模式"),
        ("auto", True, False, "自动使用默认值模式"),
    ]
    
    for mode, enabled, auto_retry, description in configs:
        config = InteractionConfig(
            enabled=enabled,
            mode=mode,
            auto_retry_on_interaction=auto_retry
        )
        print(f"✓ {description}")
        print(f"  - mode: {config.mode}")
        print(f"  - enabled: {config.enabled}")
        print(f"  - auto_retry_on_interaction: {config.auto_retry_on_interaction}")
        print()


if __name__ == "__main__":
    try:
        test_config_loading()
        test_auto_retry_handler()
        test_auto_response_handler()
        test_interaction_modes()
        
        print("=" * 60)
        print("🎉 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
