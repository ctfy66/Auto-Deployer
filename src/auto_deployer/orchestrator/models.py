"""Data models for the orchestrator module."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from ..llm.agent import DeploymentStep


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
class StepOutputs:
    """步骤的强制结构化产出
    
    每个步骤完成时必须提供此结构化产出，用于：
    1. 传递关键信息给后续步骤
    2. 更新全局执行摘要
    3. 保证跨步骤的信息一致性
    """
    # 必填：一句话总结本步骤完成了什么
    summary: str
    
    # 环境变更（会合并到 ExecutionSummary.environment）
    environment_changes: Dict[str, Any] = field(default_factory=dict)
    
    # 新增配置值（环境变量等）
    new_configurations: Dict[str, str] = field(default_factory=dict)
    
    # 创建/修改的关键文件路径
    artifacts: List[str] = field(default_factory=list)
    
    # 启动的服务列表
    # 例如: [{"name": "myapp", "port": 3000, "pid": 12345}]
    services_started: List[Dict[str, Any]] = field(default_factory=list)
    
    # 需要传递给后续步骤的自定义数据
    custom_data: Dict[str, Any] = field(default_factory=dict)
    
    # 遇到并解决的问题
    # 例如: [{"issue": "Port 3000 occupied", "resolution": "Changed to 3001"}]
    issues_resolved: List[Dict[str, str]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StepOutputs":
        """从字典创建"""
        return cls(
            summary=data.get("summary", ""),
            environment_changes=data.get("environment_changes", {}),
            new_configurations=data.get("new_configurations", {}),
            artifacts=data.get("artifacts", []),
            services_started=data.get("services_started", []),
            custom_data=data.get("custom_data", {}),
            issues_resolved=data.get("issues_resolved", []),
        )


@dataclass
class ExecutionSummary:
    """滚动更新的全局执行摘要
    
    在整个部署过程中维护，每个步骤完成后更新。
    用于为后续步骤提供全局上下文，而不需要传递完整的对话历史。
    """
    # 部署基础信息
    project_name: str
    deploy_dir: str
    strategy: str  # "docker-compose" | "traditional" | "docker" | "static"
    
    # 环境状态（随执行更新）
    # 例如: {"node_version": "18.17.0", "pm2_installed": True, "app_port": 3000}
    environment: Dict[str, Any] = field(default_factory=dict)
    
    # 已完成的关键操作（简洁列表，自动截断）
    # 例如: ["Cloned repository to ~/myapp", "Installed Node.js 18.17.0"]
    completed_actions: List[str] = field(default_factory=list)
    
    # 已确定的配置值
    # 例如: {"NODE_ENV": "production", "PORT": "3000"}
    configurations: Dict[str, str] = field(default_factory=dict)
    
    # 遇到的问题与解决方案（供后续步骤参考）
    resolved_issues: List[Dict[str, str]] = field(default_factory=list)
    
    # 最后更新时间
    last_updated: str = ""
    
    def to_prompt_context(self, max_actions: int = 10, max_issues: int = 5) -> str:
        """转换为 LLM 可读的上下文格式
        
        Args:
            max_actions: 最多显示多少条已完成操作
            max_issues: 最多显示多少条已解决问题
        """
        lines = [
            "# Current Deployment State",
            f"- Project: {self.project_name}",
            f"- Deploy Directory: {self.deploy_dir}",
            f"- Strategy: {self.strategy}",
        ]
        
        if self.environment:
            lines.append("")
            lines.append("## Environment")
            for k, v in self.environment.items():
                lines.append(f"- {k}: {v}")
        
        if self.completed_actions:
            lines.append("")
            lines.append("## Completed Actions")
            # 只显示最近的操作
            recent_actions = self.completed_actions[-max_actions:]
            for action in recent_actions:
                lines.append(f"- {action}")
            if len(self.completed_actions) > max_actions:
                omitted = len(self.completed_actions) - max_actions
                lines.append(f"  ... ({omitted} earlier actions omitted)")
        
        if self.configurations:
            lines.append("")
            lines.append("## Configurations")
            for k, v in self.configurations.items():
                # 隐藏敏感值
                display_v = v if len(v) < 50 and "password" not in k.lower() else "***"
                lines.append(f"- {k}={display_v}")
        
        if self.resolved_issues:
            lines.append("")
            lines.append("## Previously Resolved Issues")
            recent_issues = self.resolved_issues[-max_issues:]
            for issue in recent_issues:
                lines.append(f"- {issue.get('issue', 'Unknown')} → {issue.get('resolution', 'Resolved')}")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "project_name": self.project_name,
            "deploy_dir": self.deploy_dir,
            "strategy": self.strategy,
            "environment": self.environment,
            "completed_actions": self.completed_actions,
            "configurations": self.configurations,
            "resolved_issues": self.resolved_issues,
            "last_updated": self.last_updated,
        }


@dataclass
class CompressionEvent:
    """压缩事件记录
    
    记录每次历史压缩的详细信息，用于日志分析和调试
    """
    iteration: int                          # 触发压缩时的迭代次数
    commands_before: int                    # 压缩前的命令总数
    commands_compressed: int                # 被压缩的命令数
    commands_kept: int                      # 保留的最近命令数
    compressed_text_length: int             # 压缩后文本的字符长度
    token_count_before: Optional[int] = None  # 压缩前的token估算
    token_count_after: Optional[int] = None   # 压缩后的token估算
    compression_ratio: float = 0.0          # 压缩比率（节省的百分比）
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    trigger_reason: str = ""                # 触发原因
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典用于JSON序列化"""
        return {
            "iteration": self.iteration,
            "commands_before": self.commands_before,
            "commands_compressed": self.commands_compressed,
            "commands_kept": self.commands_kept,
            "compressed_text_length": self.compressed_text_length,
            "token_count_before": self.token_count_before,
            "token_count_after": self.token_count_after,
            "compression_ratio": self.compression_ratio,
            "timestamp": self.timestamp,
            "trigger_reason": self.trigger_reason,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompressionEvent":
        """从字典创建对象"""
        return cls(
            iteration=data.get("iteration", 0),
            commands_before=data.get("commands_before", 0),
            commands_compressed=data.get("commands_compressed", 0),
            commands_kept=data.get("commands_kept", 0),
            compressed_text_length=data.get("compressed_text_length", 0),
            token_count_before=data.get("token_count_before"),
            token_count_after=data.get("token_count_after"),
            compression_ratio=data.get("compression_ratio", 0.0),
            timestamp=data.get("timestamp", ""),
            trigger_reason=data.get("trigger_reason", ""),
        )


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
    
    # 压缩后的历史记录（当token达到阈值时触发）
    compressed_history: Optional[str] = None
    
    # 压缩事件记录列表（记录每次压缩的详细信息）
    compression_events: List[CompressionEvent] = field(default_factory=list)
    
    # 输出（传递给下游步骤）- 保留旧字段兼容性
    outputs: Dict[str, Any] = field(default_factory=dict)
    
    # 新增：结构化产出
    structured_outputs: Optional[StepOutputs] = None
    
    # 新增：全局执行摘要（只读引用）
    execution_summary: Optional[ExecutionSummary] = None
    
    # 新增：前置步骤的直接产出（用于强依赖场景）
    predecessor_outputs: Dict[int, StepOutputs] = field(default_factory=dict)
    
    # 错误信息
    error: Optional[str] = None


@dataclass
class StepResult:
    """步骤执行结果"""
    success: bool
    status: StepStatus
    outputs: Dict[str, Any] = field(default_factory=dict)  # 保留兼容性
    structured_outputs: Optional[StepOutputs] = None  # 新增：结构化产出
    error: Optional[str] = None
    commands_count: int = 0
    
    @classmethod
    def succeeded(
        cls, 
        outputs: Optional[Dict] = None,
        structured_outputs: Optional[StepOutputs] = None
    ) -> "StepResult":
        """创建成功结果"""
        return cls(
            success=True, 
            status=StepStatus.SUCCESS, 
            outputs=outputs or {},
            structured_outputs=structured_outputs
        )
    
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

