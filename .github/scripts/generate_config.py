#!/usr/bin/env python3
"""
GitHub Actions 配置生成脚本

根据 workflow inputs 生成适用于测试的配置文件
"""

import json
import os
import sys
from pathlib import Path


def str_to_bool(value: str) -> bool:
    """将字符串转换为布尔值"""
    if isinstance(value, bool):
        return value
    return value.lower() in ('true', '1', 'yes', 'on')


def str_to_float(value: str, default: float = 0.0) -> float:
    """将字符串转换为浮点数"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def str_to_int(value: str, default: int = 0) -> int:
    """将字符串转换为整数"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def main():
    """生成配置文件"""
    print("🔧 开始生成 GitHub Actions 配置文件...")
    
    # 获取环境变量
    llm_provider = os.getenv('INPUT_LLM_PROVIDER', 'gemini')
    llm_model = os.getenv('INPUT_LLM_MODEL', 'gemini-2.0-flash-exp')
    temperature = str_to_float(os.getenv('INPUT_TEMPERATURE', '0.0'), 0.0)
    max_iterations = str_to_int(os.getenv('INPUT_MAX_ITERATIONS', '180'), 180)
    max_iterations_per_step = str_to_int(os.getenv('INPUT_MAX_ITERATIONS_PER_STEP', '30'), 30)
    enable_planning = str_to_bool(os.getenv('INPUT_ENABLE_PLANNING', 'true'))
    require_plan_approval = str_to_bool(os.getenv('INPUT_REQUIRE_PLAN_APPROVAL', 'false'))
    planning_timeout = str_to_int(os.getenv('INPUT_PLANNING_TIMEOUT', '60'), 60)
    loop_detection_enabled = str_to_bool(os.getenv('INPUT_LOOP_DETECTION_ENABLED', 'true'))
    
    # Interaction 配置
    interaction_enabled = str_to_bool(os.getenv('INPUT_INTERACTION_ENABLED', 'true'))
    interaction_mode = os.getenv('INPUT_INTERACTION_MODE', 'cli')
    auto_retry_on_interaction = str_to_bool(os.getenv('INPUT_AUTO_RETRY_ON_INTERACTION', 'true'))
    
    # 读取默认配置作为基础
    config_dir = Path(__file__).parent.parent.parent / 'config'
    default_config_path = config_dir / 'default_config.json'
    
    if default_config_path.exists():
        with open(default_config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ 已加载默认配置: {default_config_path}")
    else:
        # 如果默认配置不存在，创建基础配置
        config = {
            "llm": {},
            "agent": {},
            "deployment": {},
            "ssh": {}
        }
        print("⚠️  未找到默认配置，使用空配置模板")
    
    # 更新 LLM 配置
    if 'llm' not in config:
        config['llm'] = {}
    
    config['llm']['provider'] = llm_provider
    config['llm']['model'] = llm_model
    config['llm']['temperature'] = temperature
    
    print(f"   LLM Provider: {llm_provider}")
    print(f"   LLM Model: {llm_model}")
    print(f"   Temperature: {temperature}")
    
    # 更新 Agent 配置
    if 'agent' not in config:
        config['agent'] = {}
    
    config['agent']['max_iterations'] = max_iterations
    config['agent']['max_iterations_per_step'] = max_iterations_per_step
    config['agent']['enable_planning'] = enable_planning
    config['agent']['require_plan_approval'] = require_plan_approval
    config['agent']['planning_timeout'] = planning_timeout
    
    print(f"   Max Iterations: {max_iterations}")
    print(f"   Max Iterations Per Step: {max_iterations_per_step}")
    print(f"   Enable Planning: {enable_planning}")
    print(f"   Require Plan Approval: {require_plan_approval}")
    print(f"   Planning Timeout: {planning_timeout}s")
    
    # 更新循环检测配置
    if 'loop_detection' not in config['agent']:
        config['agent']['loop_detection'] = {}
    
    config['agent']['loop_detection']['enabled'] = loop_detection_enabled
    print(f"   Loop Detection: {loop_detection_enabled}")
    
    # 更新 Interaction 配置
    if 'interaction' not in config:
        config['interaction'] = {}
    
    config['interaction']['enabled'] = interaction_enabled
    config['interaction']['mode'] = interaction_mode
    config['interaction']['auto_retry_on_interaction'] = auto_retry_on_interaction
    
    print(f"   Interaction Enabled: {interaction_enabled}")
    print(f"   Interaction Mode: {interaction_mode}")
    print(f"   Auto Retry On Interaction: {auto_retry_on_interaction}")
    
    # 确保配置目录存在
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存配置文件
    output_path = config_dir / 'github_actions_config.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 配置文件已生成: {output_path}")
    
    # 显示最终配置（用于调试）
    print("\n📋 最终配置内容:")
    print(json.dumps(config, indent=2, ensure_ascii=False))
    
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
