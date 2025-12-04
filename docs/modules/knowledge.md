# Knowledge 模块

经验存储与检索模块。

**模块路径**：`auto_deployer.knowledge`

---

## 概述

`knowledge` 模块实现 Agent 的经验学习系统。通过从历史部署日志中提取经验、使用 LLM 进行精炼、存储到向量数据库并在后续部署中检索相关经验，帮助 Agent 更高效地完成部署任务。

---

## 依赖

此模块需要安装可选依赖：

```bash
# 安装方式 1：使用可选依赖
pip install auto-deployer[memory]

# 安装方式 2：手动安装
pip install chromadb sentence-transformers
```

如果依赖未安装，导入模块时会抛出 `ImportError`。

---

## 数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                     Knowledge System                             │
│                                                                 │
│  agent_logs/*.json                                              │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────┐                                            │
│  │  Extractor      │  从日志提取原始经验                         │
│  │                 │  (命令序列 + 结果)                          │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  Store (raw)    │  存储原始经验                               │
│  │                 │  ChromaDB: raw_experiences                  │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  Refiner        │  使用 LLM 精炼                              │
│  │                 │  提取: 问题 → 解决方案                       │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  Store (refined)│  存储精炼经验                               │
│  │                 │  ChromaDB: refined_experiences              │
│  └────────┬────────┘                                            │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────┐                                            │
│  │  Retriever      │  语义检索相关经验                           │
│  │                 │  → 注入 Agent Prompt                        │
│  └─────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 数据模型

### RawExperience

原始经验（从日志提取）。

```python
@dataclass
class RawExperience:
    id: str
    content: str
    project_type: Optional[str]
    framework: Optional[str]
    source_log: str
    timestamp: str
```

### RefinedExperience

精炼经验（LLM 处理后）。

```python
@dataclass
class RefinedExperience:
    id: str
    content: str
    problem_summary: str
    solution_summary: str
    scope: str  # "universal" 或 "project_specific"
    project_type: Optional[str]
    framework: Optional[str]
```

---

## 类

### ExperienceStore

向量数据库存储，基于 ChromaDB。

```python
class ExperienceStore:
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
    ): ...
```

#### 构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `persist_dir` | `Optional[str]` | `.auto-deployer/knowledge` | 数据持久化目录 |
| `embedding_model` | `str` | `"all-MiniLM-L6-v2"` | Sentence Transformer 模型名称 |

#### Raw Experiences 方法

##### add_raw_experience

添加原始经验。

```python
def add_raw_experience(
    self,
    id: str,
    content: str,
    metadata: Dict[str, Any],
) -> bool
```

##### get_raw_experience

获取单个原始经验。

```python
def get_raw_experience(self, id: str) -> Optional[Dict[str, Any]]
```

##### get_all_raw_experiences

获取所有原始经验。

```python
def get_all_raw_experiences(self) -> List[Dict[str, Any]]
```

##### get_unprocessed_raw_experiences

获取未处理的原始经验。

```python
def get_unprocessed_raw_experiences(self) -> List[Dict[str, Any]]
```

##### mark_raw_as_processed

标记原始经验为已处理。

```python
def mark_raw_as_processed(self, id: str) -> bool
```

##### raw_exists

检查原始经验是否存在。

```python
def raw_exists(self, id: str) -> bool
```

##### raw_count

获取原始经验数量。

```python
def raw_count(self) -> int
```

##### search_raw

语义搜索原始经验。

```python
def search_raw(
    self,
    query: str,
    n_results: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]
```

#### Refined Experiences 方法

##### add_refined_experience

添加精炼经验。

```python
def add_refined_experience(
    self,
    id: str,
    content: str,
    metadata: Dict[str, Any],
) -> bool
```

##### get_refined_experience

获取单个精炼经验。

```python
def get_refined_experience(self, id: str) -> Optional[Dict[str, Any]]
```

##### get_all_refined_experiences

获取所有精炼经验。

```python
def get_all_refined_experiences(self) -> List[Dict[str, Any]]
```

##### search_refined

语义搜索精炼经验。

```python
def search_refined(
    self,
    query: str,
    n_results: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]
```

##### refined_exists

检查精炼经验是否存在。

```python
def refined_exists(self, id: str) -> bool
```

##### refined_count

获取精炼经验数量。

```python
def refined_count(self) -> int
```

#### 其他方法

##### get_stats

获取统计信息。

```python
def get_stats(self) -> Dict[str, Any]
```

返回：

```python
{
    "raw_count": 25,
    "refined_count": 15,
    "unprocessed_count": 10,
    "universal_count": 8,
    "project_specific_count": 7,
    "project_types": {"nodejs": 10, "python": 5},
    "persist_dir": ".auto-deployer/knowledge",
}
```

##### persist

持久化数据（PersistentClient 自动持久化，此方法保留以兼容）。

```python
def persist(self) -> None
```

---

### ExperienceExtractor

从部署日志提取经验。

```python
class ExperienceExtractor:
    def __init__(self, log_dir: Optional[str] = None): ...
```

#### 构造函数参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `log_dir` | `Optional[str]` | `./agent_logs` | 日志目录 |

#### 方法

##### extract_from_log

从单个日志文件提取经验。

```python
def extract_from_log(self, log_path: str) -> List[RawExperience]
```

##### extract_from_all_logs

从所有日志文件提取经验。

```python
def extract_from_all_logs(self) -> List[RawExperience]
```

---

### ExperienceRefiner

使用 LLM 精炼原始经验。

```python
class ExperienceRefiner:
    def __init__(self, llm): ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `llm` | LLM 客户端 | 需要有 `generate(prompt)` 方法 |

#### 方法

##### refine

精炼单个原始经验。

```python
def refine(self, raw_experience: Dict[str, Any]) -> Optional[Dict[str, Any]]
```

返回精炼后的经验字典，包含：
- `id`: 经验 ID
- `content`: 精炼后的内容
- `metadata`: 元数据（scope, problem_summary, solution_summary, ...）

---

### ExperienceRetriever

经验检索器，用于在部署时检索相关经验。

```python
class ExperienceRetriever:
    def __init__(self, store: ExperienceStore): ...
```

#### 构造函数参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `store` | `ExperienceStore` | 经验存储实例 |

#### 方法

##### get_formatted_experiences

获取格式化的相关经验（用于 Prompt）。

```python
def get_formatted_experiences(
    self,
    project_type: Optional[str] = None,
    framework: Optional[str] = None,
    query: Optional[str] = None,
    max_results: int = 10,
    max_length: int = 2000,
) -> str
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `project_type` | `Optional[str]` | 项目类型过滤 |
| `framework` | `Optional[str]` | 框架过滤 |
| `query` | `Optional[str]` | 语义搜索查询 |
| `max_results` | `int` | 最大结果数 |
| `max_length` | `int` | 最大输出长度 |

**返回**：格式化的 Markdown 字符串，可直接注入 Prompt。

---

## 使用示例

### 完整工作流

```python
from auto_deployer.knowledge import (
    ExperienceStore,
    ExperienceExtractor,
    ExperienceRefiner,
    ExperienceRetriever,
)

# 1. 创建存储
store = ExperienceStore()

# 2. 从日志提取经验
extractor = ExperienceExtractor()
raw_experiences = extractor.extract_from_all_logs()

# 3. 存储原始经验
for exp in raw_experiences:
    if not store.raw_exists(exp.id):
        store.add_raw_experience(
            id=exp.id,
            content=exp.content,
            metadata={
                "project_type": exp.project_type,
                "framework": exp.framework,
                "source_log": exp.source_log,
                "processed": "False",
            }
        )

# 4. 精炼经验（需要 LLM）
class SimpleLLM:
    def generate(self, prompt):
        # 调用 LLM API...
        pass

llm = SimpleLLM()
refiner = ExperienceRefiner(llm)

for raw in store.get_unprocessed_raw_experiences():
    refined = refiner.refine(raw)
    if refined:
        store.add_refined_experience(
            id=refined["id"],
            content=refined["content"],
            metadata=refined["metadata"]
        )
        store.mark_raw_as_processed(raw["id"])

# 5. 在部署时检索经验
retriever = ExperienceRetriever(store)
experiences_text = retriever.get_formatted_experiences(
    project_type="nodejs",
    framework="Next.js",
)
print(experiences_text)
```

### 在 Agent 中使用

```python
from auto_deployer.llm.agent import DeploymentAgent
from auto_deployer.knowledge import ExperienceStore, ExperienceRetriever

# 创建检索器
store = ExperienceStore()
retriever = ExperienceRetriever(store)

# 注入到 Agent
agent = DeploymentAgent(
    config=llm_config,
    experience_retriever=retriever,
)

# Agent 在构建 Prompt 时会自动检索相关经验
```

### 语义搜索

```python
store = ExperienceStore()

# 搜索与特定错误相关的经验
results = store.search_refined(
    query="npm install EACCES permission denied",
    n_results=5,
)

for result in results:
    print(f"问题: {result['metadata']['problem_summary']}")
    print(f"解决: {result['metadata']['solution_summary']}")
    print(f"距离: {result['distance']}")
    print("---")
```

### 按项目类型过滤

```python
# 只搜索 Node.js 相关经验
results = store.search_refined(
    query="deployment failed",
    n_results=5,
    where={"project_type": "nodejs"},
)
```

### 查看统计信息

```python
store = ExperienceStore()
stats = store.get_stats()

print(f"原始经验: {stats['raw_count']}")
print(f"精炼经验: {stats['refined_count']}")
print(f"未处理: {stats['unprocessed_count']}")
print(f"通用经验: {stats['universal_count']}")
print(f"项目特定: {stats['project_specific_count']}")
```

### CLI 使用

```bash
# 查看状态
auto-deployer memory --status

# 提取经验
auto-deployer memory --extract

# 精炼经验
auto-deployer memory --refine

# 列出经验
auto-deployer memory --list

# 导出
auto-deployer memory --export markdown
```

---

## 经验类型

### Universal（通用经验）

适用于所有项目的通用问题和解决方案：

- npm 权限问题
- Docker 镜像拉取失败
- 端口被占用
- 进程管理（nohup、后台运行）

### Project Specific（项目特定经验）

特定项目类型或框架的经验：

- Next.js 构建内存问题
- Django 静态文件配置
- FastAPI uvicorn 配置

---

## 相关文档

- [agent](agent.md) - Agent 使用 ExperienceRetriever
- [CLI 参考](../cli-reference.md) - memory 命令

