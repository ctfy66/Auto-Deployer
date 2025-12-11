# 故障排查指南

## Python 环境不一致问题

### 问题描述

在 Windows 系统上，如果安装了多个 Python 环境（如 MSYS2、Anaconda、官方 Python），可能会出现环境不一致的问题：

- `python` 命令指向一个 Python 版本（如 MSYS2 的 Python 3.11.9）
- `pip` 命令指向另一个 Python 版本（如官方 Python 3.12）
- 导致依赖包安装到错误的 Python 环境

### 影响范围

1. **运行测试失败**：`python -m tests.run_tests` 会找不到已安装的依赖
2. **CLI 命令失败**：`auto-deployer` 命令可能无法正常运行
3. **本地部署失败**：如果代码中调用 `python` 命令，会使用错误的 Python 版本
4. **依赖管理混乱**：新安装的包可能安装到错误的 Python 环境

### 诊断方法

检查当前 Python 环境：

```powershell
# 检查 python 命令指向
Get-Command python | Select-Object -ExpandProperty Source

# 检查 pip 命令指向
Get-Command pip | Select-Object -ExpandProperty Source

# 检查 Python 版本
python --version
pip --version

# 检查已安装的包
python -m pip list
```

### 解决方案

#### 方案1：使用 Python Launcher（推荐）

Windows 的 Python Launcher (`py`) 可以自动选择正确的 Python 版本：

```powershell
# 运行测试
py -3.12 -m tests.run_tests --difficulty easy

# 运行 CLI
py -3.12 -m auto_deployer.main deploy --repo <url> --local

# 安装依赖
py -3.12 -m pip install -e .
```

#### 方案2：调整 PATH 环境变量

将正确的 Python 路径放在 PATH 前面：

1. **临时调整**（当前会话）：
```powershell
# 移除 MSYS2 Python 路径
$env:PATH = ($env:PATH -split ';' | Where-Object { $_ -notlike '*msys64*' }) -join ';'

# 验证
python --version  # 应该显示 Python 3.12.x
```

2. **永久调整**：
   - 打开"系统属性" → "高级" → "环境变量"
   - 在"系统变量"中找到 `Path`
   - 将 `C:\Users\DELL\AppData\Local\Programs\Python\Python312` 移到最前面
   - 将 `C:\Users\DELL\AppData\Local\Programs\Python\Python312\Scripts` 移到最前面
   - 将 MSYS2 的 Python 路径移到后面或删除

#### 方案3：使用虚拟环境（最佳实践）

为项目创建独立的虚拟环境：

```powershell
# 使用 Python 3.12 创建虚拟环境
py -3.12 -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 安装依赖
pip install -e .

# 运行测试
python -m tests.run_tests --difficulty easy
```

#### 方案4：创建启动脚本

创建便捷的启动脚本，避免每次输入完整路径：

**`run_tests.ps1`**:
```powershell
#!/usr/bin/env pwsh
py -3.12 -m tests.run_tests $args
```

**`run_deploy.ps1`**:
```powershell
#!/usr/bin/env pwsh
py -3.12 -m auto_deployer.main deploy $args
```

使用方式：
```powershell
.\run_tests.ps1 --difficulty easy
.\run_deploy.ps1 --repo <url> --local
```

### 验证修复

修复后验证：

```powershell
# 1. 检查 Python 版本
python --version  # 应该显示 3.12.x

# 2. 检查依赖是否可用
python -c "from dotenv import load_dotenv; print('OK')"

# 3. 运行测试帮助
python -m tests.run_tests --help
```

### 预防措施

1. **使用虚拟环境**：为每个项目创建独立的虚拟环境
2. **使用 py launcher**：在 Windows 上优先使用 `py -3.12` 而不是 `python`
3. **检查 PATH 顺序**：确保正确的 Python 在 PATH 前面
4. **文档化环境**：在 README 中明确说明 Python 版本要求

## Docker 连接问题

### 问题描述

运行测试时出现错误：
```
Error while fetching server API version: (2, 'CreateFile', '系统找不到指定的文件。')
```

### 原因

Docker Desktop 未安装或未启动。测试套件需要 Docker 来创建隔离的测试环境。

### 解决方案

#### 1. 安装 Docker Desktop

**Windows/Mac**：
1. 下载：https://www.docker.com/products/docker-desktop
2. 安装并启动 Docker Desktop
3. 等待 Docker 引擎启动完成（任务栏图标显示为绿色）

**Linux**：
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 添加当前用户到 docker 组（避免每次使用 sudo）
sudo usermod -aG docker $USER
```

#### 2. 验证 Docker 安装

```powershell
# Windows
docker version
docker ps

# 测试 Docker 是否正常工作
docker run hello-world
```

#### 3. 检查 Docker Desktop 设置（Windows/Mac）

- 确保 Docker Desktop 已启动
- 检查"Settings" → "General" → "Use the WSL 2 based engine" 已启用（Windows）
- 检查"Resources" → "WSL Integration" 中启用了需要的发行版（Windows WSL2）

#### 4. 临时跳过 Docker 测试

如果暂时无法安装 Docker，可以使用 `--skip-setup` 选项：

```powershell
py -3.12 -m tests.run_tests --skip-setup
```

⚠️ **注意**：跳过 Docker 设置需要手动提供测试环境，测试可能无法正常运行。

### 常见问题

#### Docker Desktop 无法启动

1. **WSL 2 未安装**（Windows）：
   ```powershell
   wsl --install
   wsl --set-default-version 2
   ```

2. **Hyper-V 未启用**（Windows）：
   - 打开"控制面板" → "程序" → "启用或关闭 Windows 功能"
   - 勾选"Hyper-V"和"虚拟机平台"
   - 重启电脑

3. **权限不足**：
   - 以管理员身份运行 Docker Desktop

#### Docker 命令找不到

检查 Docker 是否在 PATH 中：
```powershell
# Windows
$env:PATH -split ';' | Select-String -Pattern 'docker'

# 如果没有，添加 Docker 路径到 PATH
$env:PATH += ";C:\Program Files\Docker\Docker\resources\bin"
```

