#!/usr/bin/env pwsh
# Auto-Deployer 测试运行脚本
# 使用 Python 3.12 运行测试，避免环境不一致问题

py -3.12 -m tests.run_tests $args

