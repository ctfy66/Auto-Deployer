"""测试 orchestrator 模块导入"""

print("Testing imports...")

# 测试 orchestrator 模块
from auto_deployer.orchestrator import (
    DeploymentOrchestrator,
    StepExecutor,
    DeployContext,
    StepStatus,
    StepContext,
    StepResult,
)
print("✅ Orchestrator module imported successfully")

# 测试 DeploymentPlanner
from auto_deployer.llm.agent import DeploymentPlanner, DeploymentPlan, DeploymentStep
print("✅ DeploymentPlanner imported successfully")

# 测试 workflow
from auto_deployer.workflow import DeploymentWorkflow
print("✅ Workflow imported successfully")

# 测试 config
from auto_deployer.config import AppConfig, AgentConfig
print("✅ Config imported successfully")

# 验证新配置项
agent_config = AgentConfig()
print(f"   - use_orchestrator: {agent_config.use_orchestrator}")
print(f"   - enable_planning: {agent_config.enable_planning}")

print("\n✅ All imports successful!")

