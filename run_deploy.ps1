#!/usr/bin/env pwsh
# Auto-Deployer 部署脚本
# 使用 Python 3.12 运行部署，避免环境不一致问题

py -3.12 -m auto_deployer.main deploy $args

