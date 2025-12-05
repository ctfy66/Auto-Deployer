"""Data models for the orchestrator module."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime


class StepStatus(Enum):
    """步骤执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionType(Enum):
    """LLM 决策的动作类型"""
    EXECUTE = "execute"           # 执行命令
    STEP_DONE = "step_done"       # 步骤完成
    STEP_FAILED = "step_failed"   # 步骤失败
    ASK_USER = "ask_user"         # 询问用户


@dataclass
class StepAction:
    """LLM 在步骤内的决策"""
    action_type: ActionType
    command: Optional[str] = None
    reasoning: Optional[str] = None
    message: Optional[str] = None
    question: Optional[str] = None
    options: Optional[List[str]] = None
    outputs: Optional[Dict[str, Any]] = None


@dataclass
class CommandRecord:
    """命令执行记录"""
    command: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StepContext:
    """步骤执行上下文"""
    step_id: int
    step_name: str
    goal: str
    success_criteria: str
    category: str
    
    # 执行状态
    status: StepStatus = StepStatus.PENDING
    iteration: int = 0
    max_iterations: int = 10
    
    # 执行记录
    commands: List[CommandRecord] = field(default_factory=list)
    user_interactions: List[Dict] = field(default_factory=list)
    
    # 输出（传递给下游步骤）
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    # 错误信息
    error: Optional[str] = None


@dataclass
class StepResult:
    """步骤执行结果"""
    success: bool
    status: StepStatus
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    commands_count: int = 0
    
    @classmethod
    def succeeded(cls, outputs: Optional[Dict] = None) -> "StepResult":
        """创建成功结果"""
        return cls(success=True, status=StepStatus.SUCCESS, outputs=outputs or {})
    
    @classmethod
    def failed(cls, error: str) -> "StepResult":
        """创建失败结果"""
        return cls(success=False, status=StepStatus.FAILED, error=error)
    
    @classmethod
    def skipped(cls, reason: str) -> "StepResult":
        """创建跳过结果"""
        return cls(success=True, status=StepStatus.SKIPPED, error=reason)


@dataclass
class DeployContext:
    """全局部署上下文"""
    repo_url: str
    deploy_dir: str
    host_info: Dict[str, Any]
    repo_analysis: Optional[str] = None
    project_type: Optional[str] = None
    framework: Optional[str] = None
    
    # 步骤间共享的数据
    shared_data: Dict[str, Any] = field(default_factory=dict)
    
    # 所有步骤的结果
    step_results: Dict[int, StepResult] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "repo_url": self.repo_url,
            "deploy_dir": self.deploy_dir,
            "host_info": self.host_info,
            "project_type": self.project_type,
            "framework": self.framework,
        }

