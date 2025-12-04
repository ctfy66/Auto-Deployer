# Analyzer 模块

仓库智能分析模块，提取部署相关上下文。

**模块路径**：`auto_deployer.analyzer`

---

## 概述

`analyzer` 模块负责克隆 Git 仓库并提取部署所需的上下文信息，包括项目类型、框架、关键配置文件等。这些信息会被传递给 LLM Agent，帮助其做出更准确的部署决策。

---

## 常量

### KEY_FILES

关键文件列表，按优先级排序：

```python
KEY_FILES = [
    # 部署说明
    "README.md",
    "README.rst",
    "DEPLOY.md",
    "DEPLOYMENT.md",
    
    # 包管理/依赖
    "package.json",
    "requirements.txt",
    "Pipfile",
    "pyproject.toml",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "Cargo.toml",
    "Gemfile",
    "composer.json",
    
    # 容器/部署
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
    
    # 环境配置
    ".env.example",
    ".env.sample",
    ".env.template",
    "env.example",
    
    # 构建配置
    "Makefile",
    "justfile",
    "Taskfile.yml",
    
    # 框架特定
    "vite.config.js",
    "vite.config.ts",
    "next.config.js",
    "next.config.mjs",
    "nuxt.config.js",
    "nuxt.config.ts",
    "vue.config.js",
    "angular.json",
    "webpack.config.js",
    
    # 进程管理
    "Procfile",
    "ecosystem.config.js",
    "pm2.config.js",
    
    # CI/CD
    ".github/workflows/deploy.yml",
    ".github/workflows/ci.yml",
    ".gitlab-ci.yml",
]
```

### MAX_FILE_SIZE

单文件最大读取大小：

```python
MAX_FILE_SIZE = 50 * 1024  # 50KB
```

超过此大小的文件将被跳过，避免消耗过多 Token。

---

## 类

### RepoContext

仓库分析上下文数据类。

```python
@dataclass
class RepoContext:
    repo_url: str
    project_name: str
    project_type: Optional[str] = None
    files: Dict[str, str] = field(default_factory=dict)
    directory_tree: str = ""
    detected_framework: Optional[str] = None
    detected_scripts: Dict[str, str] = field(default_factory=dict)
    detected_dependencies: List[str] = field(default_factory=list)
    summary: str = ""
```

#### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `repo_url` | `str` | 仓库 URL |
| `project_name` | `str` | 项目名称（从 URL 提取） |
| `project_type` | `Optional[str]` | 项目类型：`nodejs`、`python`、`go`、`rust`、`java`、`ruby`、`php`、`static`、`unknown` |
| `files` | `Dict[str, str]` | 关键文件内容（文件名 → 内容） |
| `directory_tree` | `str` | 目录结构树 |
| `detected_framework` | `Optional[str]` | 检测到的框架 |
| `detected_scripts` | `Dict[str, str]` | 检测到的脚本（如 npm scripts） |
| `detected_dependencies` | `List[str]` | 主要依赖列表 |
| `summary` | `str` | 分析摘要 |

#### 方法

##### to_prompt_context

将分析结果转换为 LLM Prompt 格式。

```python
def to_prompt_context(self) -> str
```

**返回**：格式化的 Markdown 字符串，包含项目概述、目录结构、可用脚本和关键文件内容。

##### to_dict

转换为字典（用于 JSON 序列化）。

```python
def to_dict(self) -> Dict[str, Any]
```

#### 示例

```python
# 访问分析结果
context = analyzer.analyze("https://github.com/user/project.git")

print(f"项目类型: {context.project_type}")
print(f"框架: {context.detected_framework}")
print(f"可用脚本: {list(context.detected_scripts.keys())}")

# 获取 Prompt 上下文
prompt_text = context.to_prompt_context()
print(prompt_text)
```

---

### RepoAnalyzer

仓库分析器。

```python
class RepoAnalyzer:
    def __init__(self, workspace_dir: Optional[str] = None): ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `workspace_dir` | `Optional[str]` | 工作目录，用于存放克隆的仓库。如果为 None，使用临时目录 |

#### 方法

##### analyze

克隆并分析仓库。

```python
def analyze(self, repo_url: str) -> RepoContext
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `repo_url` | `str` | Git 仓库 URL |

**返回**：`RepoContext` 分析结果。

**流程**：
1. 克隆仓库（浅克隆，`--depth 1`）
2. 读取关键文件
3. 生成目录树
4. 检测项目类型
5. 提取元数据
6. 生成摘要

---

## 项目类型检测规则

| 项目类型 | 检测条件 |
|----------|----------|
| `nodejs` | 存在 `package.json` |
| `python` | 存在 `requirements.txt`、`pyproject.toml` 或 `Pipfile` |
| `go` | 存在 `go.mod` |
| `rust` | 存在 `Cargo.toml` |
| `java` | 存在 `pom.xml` 或 `build.gradle` |
| `ruby` | 存在 `Gemfile` |
| `php` | 存在 `composer.json` |
| `static` | 存在 `.html` 或 `.htm` 文件 |
| `unknown` | 无法识别 |

---

## 框架检测规则

### Node.js 框架

| 框架 | 检测条件 |
|------|----------|
| Next.js | `package.json` 包含 `"next"` |
| Nuxt | `package.json` 包含 `"nuxt"` |
| Vite | `package.json` 包含 `"vite"` 或存在 `vite.config.*` |
| Vue | `package.json` 包含 `"vue"` |
| React | `package.json` 包含 `"react"` |
| Express | `package.json` 包含 `"express"` |

### Python 框架

| 框架 | 检测条件 |
|------|----------|
| Flask | `requirements.txt` 或 `pyproject.toml` 包含 `"flask"` |
| Django | 包含 `"django"` |
| FastAPI | 包含 `"fastapi"` |

---

## 使用示例

### 基本用法

```python
from auto_deployer.analyzer import RepoAnalyzer

# 使用临时目录
analyzer = RepoAnalyzer()
context = analyzer.analyze("https://github.com/vercel/next.js.git")

print(f"项目名: {context.project_name}")
print(f"类型: {context.project_type}")
print(f"框架: {context.detected_framework}")
print(f"摘要: {context.summary}")
```

### 指定工作目录

```python
# 使用指定目录（不会自动清理）
analyzer = RepoAnalyzer(workspace_dir=".auto-deployer/workspace")
context = analyzer.analyze("git@github.com:user/project.git")
```

### 检查关键文件

```python
context = analyzer.analyze(repo_url)

# 检查是否有 Docker 支持
if "Dockerfile" in context.files:
    print("支持 Docker 部署")
    print(context.files["Dockerfile"])

if "docker-compose.yml" in context.files:
    print("支持 Docker Compose 部署")
```

### 检查 npm scripts

```python
context = analyzer.analyze(repo_url)

if context.detected_scripts:
    print("可用的 npm scripts:")
    for name, cmd in context.detected_scripts.items():
        print(f"  npm run {name}: {cmd}")
    
    # 常用脚本检测
    if "build" in context.detected_scripts:
        print("✓ 有 build 脚本")
    if "start" in context.detected_scripts:
        print("✓ 有 start 脚本")
```

### 获取目录结构

```python
context = analyzer.analyze(repo_url)

print("目录结构:")
print(context.directory_tree)
```

输出示例：

```
myproject/
├── src/
│   ├── components/
│   │   ├── Header.tsx
│   │   └── Footer.tsx
│   ├── pages/
│   │   ├── index.tsx
│   │   └── about.tsx
│   └── styles/
├── public/
├── package.json
├── next.config.js
└── README.md
```

### 用于 LLM Prompt

```python
context = analyzer.analyze(repo_url)

# 获取格式化的 Prompt 上下文
prompt_context = context.to_prompt_context()

# 构建完整 Prompt
full_prompt = f"""
# 系统提示
你是一个 DevOps 部署专家...

# 仓库分析结果
{prompt_context}

# 当前状态
...
"""
```

---

## 相关文档

- [workflow](workflow.md) - 在工作流中使用 RepoAnalyzer
- [agent](agent.md) - Agent 使用 RepoContext

