# 本地分析与工作区管理规划（阶段二）

## 目标

- 在本地工作区（默认 `config.deployment.workspace_root`）中为每个部署请求准备独立目录。
- 提供 Git 仓库操作的抽象（克隆、更新、缓存），当前阶段可为占位实现，后续接入 GitPython/原生命令。
- 引入项目分析器接口，负责扫描本地仓库（如 package.json、Dockerfile、README 等），并把结构化结果交给 LLM 生成部署计划。
- 在 `DeploymentWorkflow` 中插入“准备工作区 → 本地分析 → LLM 规划”流程，保证 LLM 获得上下文。
- 设计易于扩展的结果数据结构，使未来可以逐步添加语言/框架探测器、依赖分析以及日志输出。

## 关键组件

1. **WorkspaceManager**

   - 负责在 workspace 根目录下创建临时目录（可按仓库名 + timestamp/hash）。
   - 暂时以占位操作（只创建目录并记录 repo URL）替代真实 Git 克隆，保留扩展点。
   - 提供清理接口，未来可用于磁盘回收。

2. **RepositoryAnalyzer**

   - 输入：工作区路径。
   - 输出：`RepositoryInsights`（如语言、构建系统、可能的启动命令、关键文件列表等）。
   - 当前阶段：返回基于文件存在性的简单判断（例如 package.json → Node 项目，requirements.txt → Python）。

3. **Workflow 集成**

   - `DeploymentWorkflow.run_deploy` 顺序：
     1. 调用 WorkspaceManager 准备工作区。
     2. 调用 Analyzer 生成初始洞察。
     3. 将 `DeploymentRequest + RepositoryInsights` 一并传给 LLM，供其做出决策。
   - LLM plan 中的 steps 仍可为占位（noop），但需要记录分析结果以便后续扩展。

4. **配置与 CLI**

   - 支持通过 CLI `--workspace` 参数或配置覆盖工作区根目录。
   - 可在配置中追加与工作区相关的参数（如最大缓存目录数量、是否允许复用）。当前先保留默认值。

5. **测试**
   - 为 WorkspaceManager 和 Analyzer 添加基础单元测试，确保目录创建/分析逻辑正确。

## 成功标准

- 运行 `auto-deployer deploy ...` 时能够创建本地工作目录并生成简单的分析结果。
- 单元测试覆盖配置加载、工作区准备、基础分析行为。
- 代码结构支持未来将 Git/LLM/SSH 真实逻辑无痛接入。
