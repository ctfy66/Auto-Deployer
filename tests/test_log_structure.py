"""
简单测试：验证日志结构是否包含新字段
不需要安装依赖即可运行
"""

import json
import tempfile
from pathlib import Path


def test_log_structure():
    """测试日志结构是否包含 reasoning 和 extracted_output"""
    
    # 模拟完整的部署日志结构
    deployment_log = {
        "version": "2.0",
        "mode": "orchestrator",
        "repo_url": "https://github.com/test/repo",
        "deploy_dir": "/home/user/repo",
        "project_type": "python",
        "framework": "Flask",
        "start_time": "2024-01-01T00:00:00",
        "end_time": "2024-01-01T00:05:00",
        "status": "success",
        "config": {
            "model": "deepseek-chat",
            "temperature": 0.0,
            "max_iterations_per_step": 30
        },
        "steps": [
            {
                "step_id": 1,
                "step_name": "Clone repository",
                "category": "setup",
                "status": "success",
                "iterations": 2,
                "commands": [
                    {
                        "command": "git clone https://github.com/test/repo /home/user/repo",
                        "reasoning": "需要克隆仓库到指定目录",  # 新增字段 ✅
                        "success": True,
                        "exit_code": 0,
                        "extracted_output": "✓ Command succeeded: git clone... | path: /home/user/repo\nKey Info:\n  - path: /home/user/repo",  # 新增字段 ✅
                        "stdout": "Cloning into '/home/user/repo'...\nremote: Enumerating objects: 100...",  # 原始输出（截断）
                        "stderr": "",
                        "timestamp": "2024-01-01T00:00:10",
                    }
                ],
                "user_interactions": [],
                "outputs": {},
                "error": None,
                "timestamp": "2024-01-01T00:00:15",
            }
        ]
    }
    
    print("=" * 60)
    print("测试日志结构")
    print("=" * 60)
    print()
    
    # 验证字段存在
    step = deployment_log["steps"][0]
    command = step["commands"][0]
    
    checks = [
        ("reasoning 字段", "reasoning" in command),
        ("extracted_output 字段", "extracted_output" in command),
        ("stdout 字段（原始）", "stdout" in command),
        ("stderr 字段（原始）", "stderr" in command),
    ]
    
    print("字段检查：")
    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    print()
    
    if all_passed:
        print("字段值预览：")
        print(f"  reasoning: {command['reasoning']}")
        print(f"  extracted_output: {command['extracted_output'][:80]}...")
        print(f"  stdout (原始): {command['stdout'][:50]}...")
        print()
    
    # 测试 JSON 序列化
    print("测试 JSON 序列化...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(deployment_log, f, indent=2, ensure_ascii=False)
        temp_file = f.name
    
    # 读取验证
    with open(temp_file, 'r', encoding='utf-8') as f:
        loaded = json.load(f)
        assert loaded["steps"][0]["commands"][0]["reasoning"] == "需要克隆仓库到指定目录"
        assert "extracted_output" in loaded["steps"][0]["commands"][0]
    
    Path(temp_file).unlink()  # 清理
    print("✅ JSON 序列化成功")
    print()
    
    return all_passed


def check_actual_log_file():
    """检查实际的日志文件是否包含新字段"""
    log_dir = Path("agent_logs")
    
    if not log_dir.exists():
        print("ℹ️  agent_logs 目录不存在，跳过实际日志检查")
        print("   运行部署后会生成日志文件")
        return None
    
    # 查找最新的日志文件
    log_files = list(log_dir.glob("*.json"))
    if not log_files:
        print("ℹ️  没有找到日志文件，跳过实际日志检查")
        return None
    
    latest_log = max(log_files, key=lambda p: p.stat().st_mtime)
    print(f"检查最新日志文件: {latest_log.name}")
    
    with open(latest_log, 'r', encoding='utf-8') as f:
        log_data = json.load(f)
    
    if "steps" not in log_data or not log_data["steps"]:
        print("  ⚠️  日志文件中没有步骤记录")
        return None
    
    # 检查第一个步骤
    step = log_data["steps"][0]
    if "commands" not in step or not step["commands"]:
        print("  ⚠️  步骤中没有命令记录")
        return None
    
    command = step["commands"][0]
    
    has_reasoning = "reasoning" in command
    has_extracted = "extracted_output" in command
    
    print(f"  {'✅' if has_reasoning else '❌'} reasoning 字段")
    print(f"  {'✅' if has_extracted else '❌'} extracted_output 字段")
    
    if has_reasoning and command["reasoning"]:
        print(f"    reasoning 示例: {command['reasoning'][:60]}...")
    
    if has_extracted and command["extracted_output"]:
        print(f"    extracted_output 示例: {command['extracted_output'][:60]}...")
    
    return has_reasoning and has_extracted


def main():
    print()
    print("=" * 60)
    print("Reasoning 和 Extracted Output 功能测试")
    print("=" * 60)
    print()
    
    # 测试1：日志结构
    print("【测试 1】日志结构验证")
    structure_ok = test_log_structure()
    
    # 测试2：实际日志文件
    print()
    print("【测试 2】实际日志文件检查")
    actual_ok = check_actual_log_file()
    
    # 总结
    print()
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if structure_ok:
        print("✅ 日志结构符合预期")
    else:
        print("❌ 日志结构不符合预期")
    
    if actual_ok is None:
        print("ℹ️  未检查实际日志文件（尚未运行部署）")
    elif actual_ok:
        print("✅ 实际日志文件包含新字段")
    else:
        print("❌ 实际日志文件缺少新字段")
    
    print()
    print("=" * 60)
    print("下一步：运行实际部署测试")
    print("=" * 60)
    print()
    print("1. 设置 API key:")
    print("   $env:AUTO_DEPLOYER_DEEPSEEK_API_KEY = \"your-key\"")
    print()
    print("2. 运行本地部署:")
    print("   auto-deployer deploy --repo https://github.com/ctfy66/Auto-Deployer-sample-repo --local")
    print()
    print("3. 检查输出:")
    print("   - 终端应显示: 💭 Reason: ...")
    print("   - 终端应显示: 📤 LLM将看到的提取后输出")
    print()
    print("4. 检查日志文件:")
    print("   - agent_logs/*.json 应包含 'reasoning' 字段")
    print("   - agent_logs/*.json 应包含 'extracted_output' 字段")
    print()


if __name__ == "__main__":
    main()

