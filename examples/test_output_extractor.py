"""
测试智能输出提取器的效果
展示如何从冗长的命令输出中提取关键信息
"""

import sys
import io
from pathlib import Path

# 设置UTF-8编码输出（解决Windows控制台编码问题）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 直接导入output_extractor模块，避免依赖整个包
extractor_path = Path(__file__).parent.parent / "src" / "auto_deployer" / "llm"
sys.path.insert(0, str(extractor_path))

from output_extractor import CommandOutputExtractor


def test_success_case():
    """测试成功场景：npm install"""
    print("=" * 80)
    print("测试场景 1: 成功执行 npm install")
    print("=" * 80)

    # 模拟npm install的大量输出
    stdout = """
npm WARN deprecated babel-eslint@10.1.0: babel-eslint is now @babel/eslint-parser
npm WARN deprecated core-js@2.6.12: core-js@<3.23.3 is no longer maintained
npm WARN deprecated @babel/plugin-proposal-class-properties@7.18.6: deprecated
npm WARN deprecated @babel/plugin-proposal-object-rest-spread@7.20.7: deprecated
npm notice created a lockfile as package-lock.json
added 1234 packages, and audited 1235 packages in 45s

128 packages are looking for funding
  run `npm fund` for details

3 vulnerabilities (2 moderate, 1 high)

To address all issues, run:
  npm audit fix

Run `npm audit` for details.
"""

    extractor = CommandOutputExtractor()
    extracted = extractor.extract(
        stdout=stdout,
        stderr="",
        success=True,
        exit_code=0,
        command="npm install"
    )

    print("\n【原始输出长度】:", len(stdout), "字符")
    print("\n【提取后的格式化输出】:")
    print(extractor.format_for_llm(extracted))
    print("\n【节省比例】:", f"{(1 - extracted.extracted_length / extracted.full_length) * 100:.1f}%")


def test_error_case():
    """测试失败场景：端口被占用"""
    print("\n\n" + "=" * 80)
    print("测试场景 2: 失败 - 端口被占用")
    print("=" * 80)

    stdout = """
> my-app@1.0.0 start
> node server.js

[2024-01-15T10:23:45.123Z] INFO: Starting server...
[2024-01-15T10:23:45.234Z] INFO: Loading configuration...
[2024-01-15T10:23:45.345Z] INFO: Database connection pool initialized
[2024-01-15T10:23:45.456Z] INFO: Connecting to database...
[2024-01-15T10:23:45.567Z] DEBUG: Connection string: postgresql://localhost:5432/mydb
[2024-01-15T10:23:45.678Z] INFO: Database connected successfully
[2024-01-15T10:23:45.789Z] INFO: Initializing HTTP server...
[2024-01-15T10:23:45.890Z] INFO: Attempting to bind to port 3000...
"""

    stderr = """
Error: listen EADDRINUSE: address already in use :::3000
    at Server.setupListenHandle [as _listen2] (net.js:1318:16)
    at listenInCluster (net.js:1366:12)
    at Server.listen (net.js:1452:7)
    at Function.listen (/app/node_modules/express/lib/application.js:618:24)
    at Object.<anonymous> (/app/server.js:45:5)
    at Module._compile (internal/modules/cjs/loader.js:1085:14)
"""

    extractor = CommandOutputExtractor()
    extracted = extractor.extract(
        stdout=stdout,
        stderr=stderr,
        success=False,
        exit_code=1,
        command="npm start"
    )

    print("\n【原始输出长度】:", len(stdout + stderr), "字符")
    print("\n【提取后的格式化输出】:")
    print(extractor.format_for_llm(extracted))
    print("\n【节省比例】:", f"{(1 - extracted.extracted_length / extracted.full_length) * 100:.1f}%")


def test_large_log_case():
    """测试大日志场景：构建输出"""
    print("\n\n" + "=" * 80)
    print("测试场景 3: 大量日志输出 - Docker build")
    print("=" * 80)

    # 模拟Docker build的海量输出
    stdout = """
Sending build context to Docker daemon  125.4MB
Step 1/15 : FROM node:16-alpine AS builder
16-alpine: Pulling from library/node
""" + "\n".join([f"[{i}/100] Downloading layer {i}..." for i in range(1, 101)]) + """
Successfully pulled node:16-alpine
Step 2/15 : WORKDIR /app
 ---> Running in abc123def456
Removing intermediate container abc123def456
 ---> 789ghi012jkl
Step 3/15 : COPY package*.json ./
 ---> 345mno678pqr
Step 4/15 : RUN npm ci --only=production
""" + "\n".join([f"npm http fetch GET 200 https://registry.npmjs.org/package-{i}" for i in range(1, 201)]) + """
added 1500 packages in 120s
Step 5/15 : COPY . .
 ---> 901stu234vwx
Step 15/15 : CMD ["node", "server.js"]
 ---> Running in 567yza890bcd
Removing intermediate container 567yza890bcd
 ---> 234efg567hij
Successfully built 234efg567hij
Successfully tagged myapp:latest
"""

    extractor = CommandOutputExtractor()
    extracted = extractor.extract(
        stdout=stdout,
        stderr="",
        success=True,
        exit_code=0,
        command="docker build -t myapp ."
    )

    print("\n【原始输出长度】:", len(stdout), "字符")
    print("\n【提取后的格式化输出】:")
    print(extractor.format_for_llm(extracted))
    print("\n【节省比例】:", f"{(1 - extracted.extracted_length / extracted.full_length) * 100:.1f}%")


def test_permission_error():
    """测试权限错误"""
    print("\n\n" + "=" * 80)
    print("测试场景 4: 权限错误")
    print("=" * 80)

    stderr = """
mkdir: cannot create directory '/opt/app': Permission denied
"""

    extractor = CommandOutputExtractor()
    extracted = extractor.extract(
        stdout="",
        stderr=stderr,
        success=False,
        exit_code=1,
        command="mkdir /opt/app"
    )

    print("\n【原始输出长度】:", len(stderr), "字符")
    print("\n【提取后的格式化输出】:")
    print(extractor.format_for_llm(extracted))


def test_successful_deployment():
    """测试成功的部署输出"""
    print("\n\n" + "=" * 80)
    print("测试场景 5: 成功部署并启动服务")
    print("=" * 80)

    stdout = """
[PM2] Starting /app/server.js in cluster_mode (1 instance)
[PM2] Done.
┌─────┬────────────┬─────────────┬─────────┬─────────┬──────────┬────────┬──────┬───────────┬──────────┬──────────┬──────────┬──────────┐
│ id  │ name       │ namespace   │ version │ mode    │ pid      │ uptime │ ↺    │ status    │ cpu      │ mem      │ user     │ watching │
├─────┼────────────┼─────────────┼─────────┼─────────┼──────────┼────────┼──────┼───────────┼──────────┼──────────┼──────────┼──────────┤
│ 0   │ myapp      │ default     │ 1.0.0   │ cluster │ 12345    │ 0s     │ 0    │ online    │ 0%       │ 45.2mb   │ ubuntu   │ disabled │
└─────┴────────────┴─────────────┴─────────┴─────────┴──────────┴────────┴──────┴───────────┴──────────┴──────────┴──────────┴──────────┘

Server started successfully!
Listening on http://localhost:3000
Process ID: 12345
"""

    extractor = CommandOutputExtractor()
    extracted = extractor.extract(
        stdout=stdout,
        stderr="",
        success=True,
        exit_code=0,
        command="pm2 start server.js --name myapp"
    )

    print("\n【原始输出长度】:", len(stdout), "字符")
    print("\n【提取后的格式化输出】:")
    print(extractor.format_for_llm(extracted))
    print("\n【节省比例】:", f"{(1 - extracted.extracted_length / extracted.full_length) * 100:.1f}%")


if __name__ == "__main__":
    test_success_case()
    test_error_case()
    test_large_log_case()
    test_permission_error()
    test_successful_deployment()

    print("\n\n" + "=" * 80)
    print("总结")
    print("=" * 80)
    print("""
智能输出提取器的核心优势:

1. ✅ 成功时只保留关键信息 (端口、PID、URL等)
2. ✅ 失败时精确提取错误类型和上下文
3. ✅ 自动过滤噪音日志 (DEBUG、空行、分隔线等)
4. ✅ 大幅减少token消耗 (通常节省60-90%)
5. ✅ 保留完整语义信息,不会丢失关键细节

对比传统截断方式:
- 传统: 简单截断前N个字符 → 可能丢失关键错误信息
- 智能: 根据成功/失败智能提取 → 始终保留最重要的信息
    """)
