"""测试用户介入后跳过循环检测的功能"""

from src.auto_deployer.orchestrator.loop_intervention import LoopInterventionManager


def test_user_intervention_skip():
    """测试用户介入后跳过循环检测"""
    manager = LoopInterventionManager()
    
    # 初始状态：不应该跳过
    assert not manager.should_skip_detection(), "初始状态应该不跳过"
    assert manager.skip_detection_count == 0
    
    # 激活用户介入模式
    manager.activate_user_intervention_mode()
    
    # 应该跳过，计数为5
    assert manager.should_skip_detection(), "激活后应该跳过"
    assert manager.skip_detection_count == 5
    
    # 消耗跳过计数
    for i in range(5, 0, -1):
        assert manager.should_skip_detection(), f"还有{i}次应该跳过"
        assert manager.skip_detection_count == i
        manager.consume_skip_count()
    
    # 全部消耗完，不应该再跳过
    assert not manager.should_skip_detection(), "消耗完毕后不应该跳过"
    assert manager.skip_detection_count == 0
    
    print("✅ 测试通过：用户介入后正确跳过5个指令的循环检测")


def test_reset_clears_skip_count():
    """测试重置会清空跳过计数"""
    manager = LoopInterventionManager()
    
    # 激活跳过模式
    manager.activate_user_intervention_mode()
    assert manager.skip_detection_count == 5
    
    # 重置
    manager.reset()
    
    # 跳过计数应该被清空
    assert manager.skip_detection_count == 0
    assert not manager.should_skip_detection()
    
    print("✅ 测试通过：重置正确清空跳过计数")


def test_skip_constant():
    """测试跳过常量设置正确"""
    assert LoopInterventionManager.SKIP_AFTER_USER_INTERVENTION == 5
    print("✅ 测试通过：跳过常量为5")


if __name__ == "__main__":
    test_skip_constant()
    test_user_intervention_skip()
    test_reset_clears_skip_count()
    print("\n🎉 所有测试通过！")
