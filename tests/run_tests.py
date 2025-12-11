#!/usr/bin/env python3
"""真实部署测试运行脚本"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.real_deployment.test_suite import main

if __name__ == "__main__":
    main()

