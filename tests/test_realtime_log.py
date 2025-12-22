"""测试实时日志写入功能

此脚本验证日志文件在命令执行后立即更新，而不是等到步骤结束。
"""

import json
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def watch_log_file(log_file: Path, duration: int = 30):
    """监控日志文件的变化"""
    print(f"\n{'='*60}")
    print(f"监控日志文件: {log_file.name}")
    print(f"监控时长: {duration}秒")
    print(f"{'='*60}\n")
    
    last_command_count = 0
    last_modified = None
    
    start_time = time.time()
    
    while time.time() - start_time < duration:
        if not log_file.exists():
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ 等待日志文件创建...")
            time.sleep(1)
            continue
        
        # 检查文件修改时间
        current_modified = log_file.stat().st_mtime
        if last_modified != current_modified:
            last_modified = current_modified
            
            # 读取日志内容
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                
                # 统计命令数量
                total_commands = 0
                for step in log_data.get("steps", []):
                    total_commands += len(step.get("commands", []))
                
                if total_commands > last_command_count:
                    new_commands = total_commands - last_command_count
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ 日志已更新! 新增 {new_commands} 条命令记录")
                    print(f"   总命令数: {last_command_count} → {total_commands}")
                    
                    # 显示最新命令
                    for step in log_data.get("steps", []):
                        if step.get("commands"):
                            latest_cmd = step["commands"][-1]
                            print(f"   最新命令: {latest_cmd['command'][:60]}...")
                            print(f"   状态: {'✓' if latest_cmd['success'] else '✗'} (exit_code: {latest_cmd['exit_code']})")
                    
                    last_command_count = total_commands
                    print()
                
            except json.JSONDecodeError as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ JSON解析错误 (可能正在写入): {e}")
            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ 错误: {e}")
        
        time.sleep(0.5)
    
    print(f"\n{'='*60}")
    print(f"监控结束")
    print(f"{'='*60}\n")


def main():
    """主函数"""
    log_dir = Path("agent_logs")
    
    if not log_dir.exists():
        print("❌ agent_logs 目录不存在")
        return 1
    
    # 获取最新的日志文件
    log_files = sorted(log_dir.glob("deploy_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not log_files:
        print("❌ 没有找到日志文件")
        return 1
    
    latest_log = log_files[0]
    
    print("\n" + "="*60)
    print("实时日志写入功能测试")
    print("="*60)
    print()
    print("📝 此测试验证日志文件是否在每次命令执行后立即更新")
    print()
    print("请在另一个终端运行部署命令:")
    print("  auto-deployer deploy --repo git@github.com:ctfy66/Auto-Deployer-sample-repo.git --local")
    print()
    print(f"当前监控的日志文件: {latest_log.name}")
    print()
    
    input("按 Enter 开始监控...")
    
    try:
        watch_log_file(latest_log, duration=60)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断监控")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
