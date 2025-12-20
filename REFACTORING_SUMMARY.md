# 重构总结：移除Legacy Agent模式

**日期**: 2025-12-20

## 概述

本次重构完全移除了legacy execution agent模式，使Auto-Deployer完全采用plan-execute分离架构。

## 主要改动

### 1. 删除的文件

- `src/auto_deployer/prompts/execution_agent.py` - Legacy agent的提示模板

### 2. 重构的核心文件

#### `src/auto_deployer/llm/agent.py`
- **删除**：整个`DeploymentAgent`类及其所有方法（deploy, deploy_local, _think, _execute_command等）
- **保留**：`DeploymentPlanner`类和数据类（DeploymentPlan, DeploymentStep）
- **简化**：移除了约2000+行的legacy agent代码

#### `src/auto_deployer/workflow.py`
- **删除**：`_run_legacy_agent_mode()`方法
- **删除**：`_run_local_legacy_agent_mode()`方法
- **简化**：`_run_agent_mode()`和`_run_local_agent_mode()`直接调用orchestrator模式
- **移除**：所有enable_planning相关的判断逻辑

#### `src/auto_deployer/config.py`
- **删除**：`AgentConfig.enable_planning`字段
- **保留**：
  - `max_iterations` - 用于步骤迭代预算分配
  - `max_iterations_per_step` - 每个步骤的最大迭代次数
  - `require_plan_approval` - 是否需要用户批准计划
  - `planning_timeout` - 规划超时时间

#### `config/default_config.json`
- **删除**：`"enable_planning": true`配置项

#### `src/auto_deployer/llm/__init__.py`
- **删除**：`DeploymentAgent`的导入和导出
- **保留**：`DeploymentPlanner`

#### `src/auto_deployer/cli.py`
- **删除**：未使用的`from .llm.agent import DeploymentAgent`导入

### 3. 更新的文档

#### `CLAUDE.md`
- 更新架构描述，移除"两相"改为"plan-execute"
- 移除enable_planning配置说明
- 移除Orchestrator vs Legacy对比
- 更新组件列表

#### `docs/modules/agent.md`
- 完全重写，聚焦于DeploymentPlanner
- 删除DeploymentAgent相关文档
- 添加DeploymentStep和DeploymentPlan详细说明
- 添加规划流程说明和示例输出

#### `docs/architecture.md`
- 更新核心设计理念
- 更新工作流程描述

## 架构变更

### 之前（双模式）

```
DeploymentWorkflow
  ├─ [if enable_planning=true] Orchestrator Mode
  │    ├─ DeploymentPlanner (生成计划)
  │    └─ DeploymentOrchestrator (执行计划)
  └─ [if enable_planning=false] Legacy Mode
       └─ DeploymentAgent (单循环执行)
```

### 现在（单一模式）

```
DeploymentWorkflow
  ├─ DeploymentPlanner (生成计划)
  └─ DeploymentOrchestrator (执行计划)
```

## 优势

1. **代码更简洁**：移除了约2000+行legacy代码
2. **架构更清晰**：单一的plan-execute模式，不需要模式切换逻辑
3. **维护更容易**：不需要同时维护两套执行路径
4. **控制更精细**：步骤级的迭代控制和失败恢复
5. **可读性更好**：部署计划直观展示，用户可预览和审批

## 兼容性影响

### 配置文件
- 旧配置中的`enable_planning`字段将被忽略（不会报错）
- 其他配置项保持兼容

### API
- `DeploymentWorkflow`的公共接口保持不变
- 移除的`DeploymentAgent`类可能影响直接使用该类的代码

## 测试建议

运行完整的测试套件确保功能正常：

```bash
# 运行单元测试
py -3.12 -m tests.run_tests

# 运行集成测试
python -m tests.real_deployment.test_suite
```

## 后续优化建议

1. ✅ 删除legacy相关的测试用例（如果存在）
2. ✅ 更新剩余文档中的legacy引用
3. 考虑优化步骤执行日志格式
4. 考虑增强计划生成的鲁棒性

