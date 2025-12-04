# CLI 命令参考

Auto-Deployer 提供三个主要命令：`deploy`、`logs` 和 `memory`。

## 全局选项

这些选项可用于所有子命令：

| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--config <path>` | 指定配置文件路径 | `config/default_config.json` |
| `--workspace <path>` | 本地仓库分析的工作目录 | `.auto-deployer/workspace` |

---

## deploy 命令

### 概述

`deploy` 命令用于部署 Git 仓库到目标环境。支持两种模式：

- **SSH 远程部署**：部署到远程 Linux 服务器
- **本地部署**：在本机部署（支持 Windows/Linux/Mac）

### SSH 远程部署

```bash
auto-deployer deploy --repo <URL> --host <HOST> --user <USER> --auth-method <METHOD> [OPTIONS]
```

#### 必需参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--repo <URL>` | Git 仓库 URL（支持 SSH 和 HTTPS） | `git@github.com:user/project.git` |
| `--host <HOST>` | 目标服务器地址 | `192.168.1.100` |
| `--user <USER>` | SSH 用户名 | `deploy` |
| `--auth-method <METHOD>` | 认证方式：`password` 或 `key` | `password` |

#### 可选参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--port <PORT>` | SSH 端口 | `22` |
| `--password <PWD>` | SSH 密码（`auth-method=password` 时必需） | - |
| `--key-path <PATH>` | SSH 私钥路径（`auth-method=key` 时必需） | - |
| `--deploy-dir <DIR>` | 目标部署目录 | `~/<repo_name>` |

#### 示例：密码认证

```bash
auto-deployer deploy \
    --repo git@github.com:myorg/myapp.git \
    --host 192.168.1.100 \
    --user deploy \
    --auth-method password \
    --password "my-secure-password"
```

#### 示例：密钥认证

```bash
auto-deployer deploy \
    --repo https://github.com/myorg/myapp.git \
    --host production.example.com \
    --user ubuntu \
    --auth-method key \
    --key-path ~/.ssh/id_rsa \
    --deploy-dir /var/www/myapp
```

#### 示例：使用环境变量

```bash
# 设置环境变量
export AUTO_DEPLOYER_SSH_HOST=192.168.1.100
export AUTO_DEPLOYER_SSH_USERNAME=deploy
export AUTO_DEPLOYER_SSH_PASSWORD=secret
export AUTO_DEPLOYER_GEMINI_API_KEY=your-api-key

# 简化的命令
auto-deployer deploy --repo git@github.com:myorg/myapp.git
```

---

### 本地部署

```bash
auto-deployer deploy --repo <URL> --local [OPTIONS]
```

#### 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--repo <URL>` | Git 仓库 URL | 必需 |
| `--local` 或 `-L` | 启用本地部署模式 | - |
| `--deploy-dir <DIR>` | 本地部署目录 | `~/<repo_name>` |

#### 示例：本地部署

```bash
# 基本用法
auto-deployer deploy --repo https://github.com/myorg/myapp.git --local

# 指定部署目录
auto-deployer deploy \
    --repo git@github.com:myorg/myapp.git \
    --local \
    --deploy-dir D:\Projects\myapp
```

#### Windows 注意事项

在 Windows 上，Agent 会自动使用 PowerShell 执行命令。确保：

- PowerShell 可用（Windows 10+ 默认包含）
- 已安装必要的开发工具（Node.js、Python、Git 等）
- 路径使用正斜杠 `/` 或双反斜杠 `\\`

---

## logs 命令

查看和管理 Agent 部署日志。

### 列出所有日志

```bash
auto-deployer logs --list
# 或
auto-deployer logs -l
```

输出示例：

```
📁 Agent logs in: D:\project\agent_logs

#    Status       Repository                     Time                 File
----------------------------------------------------------------------------------------------------
1    ✅ success   myapp                          2024-12-01 10:05:30  deploy_myapp_20241201_100000.json
2    ❌ failed    another-app                    2024-11-30 15:20:00  deploy_another-app_20241130_152000.json
3    🔄 running   test-project                   2024-11-30 14:00:00  deploy_test-project_20241130_140000.json
```

### 查看最新日志

```bash
# 查看最新的部署日志（完整输出）
auto-deployer logs

# 或显式指定
auto-deployer logs --latest
```

### 查看指定日志

```bash
# 通过文件名
auto-deployer logs --file deploy_myapp_20241201_100000.json
# 或
auto-deployer logs -f deploy_myapp_20241201_100000.json
```

### 摘要模式

只显示每个步骤的命令和结果，不显示详细输出：

```bash
auto-deployer logs --summary
# 或
auto-deployer logs -s
```

### 日志输出说明

```
============================================================
📄 Deployment Log: deploy_myapp_20241201_100000.json
============================================================
🔗 Repository: https://github.com/myorg/myapp.git
🖥️  Target:     deploy@192.168.1.100:22
⏰ Started:    2024-12-01T10:00:00
⏱️  Ended:      2024-12-01T10:05:30
✅ Status:     success
📊 Steps:      15
============================================================

[1] ✓ EXECUTE
    💭 首先克隆仓库到服务器
    $ git clone https://github.com/myorg/myapp.git ~/myapp
    Exit: 0
    │ Cloning into '/home/deploy/myapp'...

[2] ✓ EXECUTE
    💭 安装依赖
    $ cd ~/myapp && npm install
    Exit: 0
    │ added 150 packages in 10s
    │ ... (8 lines total)

...

[15] ✅ DONE
    📝 应用已成功部署，运行在 http://192.168.1.100:3000
```

---

## memory 命令

管理 Agent 的经验记忆系统。

> **注意**：此功能需要安装可选依赖：
> ```bash
> pip install auto-deployer[memory]
> # 或
> pip install chromadb sentence-transformers
> ```

### 查看状态

```bash
auto-deployer memory --status
```

输出示例：

```
==================================================
🧠 Agent Memory Status
==================================================
📁 Storage:         .auto-deployer/knowledge
📥 Raw experiences: 25
   └ Unprocessed:   10
📊 Refined:         15
   ├ Universal:     8
   └ Proj-specific: 7

📦 By Project Type:
   • nodejs: 10
   • python: 5
==================================================
```

### 提取经验

从部署日志中提取原始经验：

```bash
auto-deployer memory --extract
```

输出：

```
📤 Extracting experiences from deployment logs...
✅ Extracted: 5 new, 3 already exist
```

### 精炼经验

使用 LLM 将原始经验转换为结构化的问题-解决方案对：

```bash
auto-deployer memory --refine
```

输出：

```
🔄 Refining 10 experiences with LLM...
  Processing: a1b2c3d4e5f6... ✓ [universal]
  Processing: f6e5d4c3b2a1... ✓ [project_specific]
  ...

✅ Refined 8/10 experiences
```

### 列出经验

```bash
auto-deployer memory --list
# 或
auto-deployer memory -l
```

输出：

```
======================================================================
🧠 Stored Experiences (15 total)
======================================================================

 1. 🌍 [UNIVERSAL] npm install 失败：EACCES 权限问题
    💡 Solution: 使用 npm config set prefix ~/.npm-global 避免全局安装权限问题
    🏷️  Tags: nodejs

 2. 📦 [PROJECT_SPECIFIC] Next.js 构建时内存不足
    💡 Solution: 设置 NODE_OPTIONS=--max_old_space_size=4096
    🏷️  Tags: nodejs, Next.js

...

======================================================================
💡 Use `auto-deployer memory --show N` to view details of experience #N
💡 Use `auto-deployer memory --export markdown` to export all memories
======================================================================
```

### 查看详情

```bash
auto-deployer memory --show 1
```

输出：

```
======================================================================
🧠 Experience #1 - Detailed View
======================================================================

📋 ID:           exp_a1b2c3d4e5f6
🏷️  Scope:        universal
📦 Project Type: nodejs
🔧 Framework:    N/A
📅 Source Log:   deploy_myapp_20241201_100000.json

----------------------------------------------------------------------
❌ PROBLEM:
----------------------------------------------------------------------
   npm install 失败，错误信息：EACCES permission denied

----------------------------------------------------------------------
✅ SOLUTION:
----------------------------------------------------------------------
   使用 npm config set prefix ~/.npm-global 配置 npm 全局安装路径

----------------------------------------------------------------------
📝 FULL EXPERIENCE:
----------------------------------------------------------------------
   当在服务器上运行 npm install -g 时遇到权限问题...
   解决步骤：
   1. mkdir ~/.npm-global
   2. npm config set prefix ~/.npm-global
   3. export PATH=~/.npm-global/bin:$PATH
   ...

======================================================================
```

### 导出经验

导出为 JSON：

```bash
auto-deployer memory --export json
```

导出为 Markdown：

```bash
auto-deployer memory --export markdown
# 或
auto-deployer memory --export md
```

输出文件保存在 `.auto-deployer/memory/` 目录下。

### 清除经验

```bash
auto-deployer memory --clear
```

需要输入 `yes` 确认。

---

## 环境变量

Auto-Deployer 支持通过环境变量配置。可以直接设置或使用 `.env` 文件。

### LLM 配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `AUTO_DEPLOYER_GEMINI_API_KEY` | Gemini API 密钥 | `AIza...` |
| `AUTO_DEPLOYER_OPENAI_API_KEY` | OpenAI API 密钥 | `sk-...` |
| `AUTO_DEPLOYER_LLM_PROXY` | LLM API 代理 | `http://127.0.0.1:7890` |

### SSH 配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `AUTO_DEPLOYER_SSH_HOST` | 默认 SSH 主机 | `192.168.1.100` |
| `AUTO_DEPLOYER_SSH_PORT` | 默认 SSH 端口 | `22` |
| `AUTO_DEPLOYER_SSH_USERNAME` | 默认用户名 | `deploy` |
| `AUTO_DEPLOYER_SSH_PASSWORD` | 默认密码 | `secret` |
| `AUTO_DEPLOYER_SSH_KEY_PATH` | 默认私钥路径 | `~/.ssh/id_rsa` |

### 代理配置

| 变量名 | 说明 |
|--------|------|
| `HTTP_PROXY` | HTTP 代理（也用于 LLM API） |
| `HTTPS_PROXY` | HTTPS 代理 |

### .env 文件示例

在项目根目录创建 `.env` 文件：

```bash
# LLM API 配置
AUTO_DEPLOYER_GEMINI_API_KEY=AIzaSyB...

# SSH 默认配置
AUTO_DEPLOYER_SSH_HOST=192.168.1.100
AUTO_DEPLOYER_SSH_USERNAME=deploy
AUTO_DEPLOYER_SSH_PASSWORD=my-password

# 代理设置（可选）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

---

## 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `1` | 失败 |

### 常见失败场景

| 场景 | 说明 |
|------|------|
| 缺少必需参数 | SSH 模式缺少 `--host`、`--user` 等 |
| SSH 连接失败 | 无法连接到目标服务器 |
| 认证失败 | 密码错误或密钥无效 |
| Agent 放弃 | LLM 决定无法继续部署 |
| 达到最大迭代 | 超过 `max_iterations` 仍未完成 |
| 用户取消 | 在交互过程中按 Ctrl+C |

---

## 使用技巧

### 1. 使用 .env 文件管理敏感信息

避免在命令行中暴露密码：

```bash
# 不推荐（密码会出现在 shell 历史中）
auto-deployer deploy --password "secret" ...

# 推荐：使用 .env 文件或环境变量
export AUTO_DEPLOYER_SSH_PASSWORD="secret"
auto-deployer deploy ...
```

### 2. 结合 Shell 脚本批量部署

```bash
#!/bin/bash
SERVERS=("server1.example.com" "server2.example.com" "server3.example.com")

for server in "${SERVERS[@]}"; do
    echo "Deploying to $server..."
    auto-deployer deploy \
        --repo git@github.com:myorg/myapp.git \
        --host "$server" \
        --user deploy \
        --auth-method key \
        --key-path ~/.ssh/deploy_key
done
```

### 3. 日志分析技巧

```bash
# 查找所有失败的部署
auto-deployer logs --list | grep failed

# 使用 jq 分析 JSON 日志
cat agent_logs/deploy_myapp_*.json | jq '.steps | length'

# 统计命令执行次数
cat agent_logs/deploy_myapp_*.json | jq '[.steps[] | select(.action=="execute")] | length'
```

### 4. 调试部署问题

```bash
# 查看完整日志（不是摘要）
auto-deployer logs --latest

# 检查 Agent 的推理过程
cat agent_logs/deploy_*.json | jq '.steps[] | {reasoning, command, result}'
```

### 5. 与 CI/CD 集成

GitLab CI 示例：

```yaml
deploy:
  stage: deploy
  script:
    - pip install auto-deployer
    - auto-deployer deploy
        --repo $CI_REPOSITORY_URL
        --host $DEPLOY_HOST
        --user $DEPLOY_USER
        --auth-method key
        --key-path $SSH_PRIVATE_KEY_PATH
  only:
    - main
```

GitHub Actions 示例：

```yaml
- name: Deploy with Auto-Deployer
  env:
    AUTO_DEPLOYER_GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    AUTO_DEPLOYER_SSH_HOST: ${{ secrets.DEPLOY_HOST }}
    AUTO_DEPLOYER_SSH_USERNAME: ${{ secrets.DEPLOY_USER }}
    AUTO_DEPLOYER_SSH_PASSWORD: ${{ secrets.DEPLOY_PASSWORD }}
  run: |
    pip install auto-deployer
    auto-deployer deploy --repo ${{ github.server_url }}/${{ github.repository }}.git
```

