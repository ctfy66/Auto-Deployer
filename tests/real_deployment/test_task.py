"""测试任务封装 - 定义测试任务的数据结构"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional

from .test_projects import TestProject


@dataclass
class TestTask:
    """测试任务配置"""
    project: TestProject
    env_config: Dict[str, Any]
    local_mode: bool
    attempt: int = 1  # 当前尝试次数
    max_attempts: int = 2  # 最大尝试次数（默认可重试1次）
    task_id: str = field(default_factory=lambda: generate_task_id())
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def is_first_attempt(self) -> bool:
        """是否是第一次尝试"""
        return self.attempt == 1
    
    def can_retry(self) -> bool:
        """是否还可以重试"""
        return self.attempt < self.max_attempts
    
    def next_attempt(self) -> "TestTask":
        """创建下一次重试的任务"""
        return TestTask(
            project=self.project,
            env_config=self.env_config,
            local_mode=self.local_mode,
            attempt=self.attempt + 1,
            max_attempts=self.max_attempts,
            task_id=self.task_id,  # 保持相同的task_id
            created_at=self.created_at
        )


def generate_task_id() -> str:
    """
    生成唯一的任务ID
    
    格式: task_<timestamp>_<short_uuid>
    例如: task_20251221_103045_a3b2c1
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = str(uuid.uuid4())[:6]
    return f"task_{timestamp}_{short_uuid}"
