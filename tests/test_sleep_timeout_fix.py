"""测试 sleep 命令的超时修复 - 简化版本（直接测试正则表达式匹配）"""
import re


def get_smart_timeout_simplified(command: str) -> tuple[int, int]:
    """
    简化版本的 _get_smart_timeout 方法（用于测试）
    复制自 step_executor.py 的实现
    """
    # 默认值
    timeout = 600        # 10分钟
    idle_timeout = 60    # 1分钟
    
    # 检测sleep/wait命令，延长总超时和空闲超时
    sleep_patterns = [
        r'sleep\s+(\d+)',                    # Linux: sleep 300
        r'Start-Sleep\s+-Seconds\s+(\d+)',   # PowerShell: Start-Sleep -Seconds 300
        r'timeout\s+/t\s+(\d+)',             # Windows CMD: timeout /t 300
    ]
    for pattern in sleep_patterns:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            sleep_duration = int(match.group(1))
            # 总超时 = sleep时间 + 120秒余量
            timeout = max(timeout, sleep_duration + 120)
            # 空闲超时 = sleep时间 + 30秒余量（允许sleep命令完整执行）
            idle_timeout = max(idle_timeout, sleep_duration + 30)
            break
    
    return timeout, idle_timeout


def test_sleep_timeout_fix():
    """测试 _get_smart_timeout 方法对 sleep 命令的处理"""
    
    # 测试用例：命令 -> (期望的timeout, 期望的idle_timeout)
    test_cases = [
        # PowerShell sleep 命令
        ("Start-Sleep -Seconds 60", (600, 90)),      # max(600, 180)=600, max(60, 90)=90
        ("Start-Sleep -Seconds 180", (600, 210)),    # max(600, 300)=600, max(60, 210)=210
        ("Start-Sleep -Seconds 300", (600, 330)),    # max(600, 420)=600, max(60, 330)=330
        
        # Linux sleep 命令
        ("sleep 120", (600, 150)),                   # max(600, 240)=600, max(60, 150)=150
        ("sleep 90", (600, 120)),                    # max(600, 210)=600, max(60, 120)=120
        
        # Windows CMD timeout 命令
        ("timeout /t 90", (600, 120)),               # max(600, 210)=600, max(60, 120)=120
        
        # 组合命令
        ("docker logs xxx; Start-Sleep -Seconds 180", (600, 210)),
        
        # 短 sleep（小于默认值）
        ("Start-Sleep -Seconds 30", (600, 60)),      # max(600, 150)=600, max(60, 60)=60
        
        # 长 sleep（超过默认值 600s）
        ("Start-Sleep -Seconds 700", (820, 730)),    # max(600, 820)=820, max(60, 730)=730
        
        # 非 sleep 命令（应该使用默认值）
        ("docker ps", (600, 60)),
        ("ls -la", (600, 60)),
    ]
    
    print("=" * 80)
    print("测试 sleep 命令超时修复")
    print("=" * 80)
    
    all_passed = True
    for command, (expected_timeout, expected_idle_timeout) in test_cases:
        actual_timeout, actual_idle_timeout = get_smart_timeout_simplified(command)
        
        passed = (actual_timeout == expected_timeout and 
                  actual_idle_timeout == expected_idle_timeout)
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"\n{status}")
        print(f"  命令: {command}")
        print(f"  期望: timeout={expected_timeout}s, idle_timeout={expected_idle_timeout}s")
        print(f"  实际: timeout={actual_timeout}s, idle_timeout={actual_idle_timeout}s")
        
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ 所有测试通过！")
        return 0
    else:
        print("❌ 部分测试失败！")
        return 1


if __name__ == "__main__":
    exit_code = test_sleep_timeout_fix()
    exit(exit_code)
