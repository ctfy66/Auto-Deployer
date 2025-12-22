"""Loop intervention management for deployment execution.

This module handles interventions when loops are detected, including
temperature boosting, reflection injection, and user interaction.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import LoopDetectionResult

logger = logging.getLogger(__name__)


class LoopInterventionManager:
    """循环干预管理器
    
    当检测到循环时，采取分级干预措施：
    1. 第一次：提升温度，增加随机性
    2. 第二次：注入反思提示，强制Agent重新思考
    3. 第三次及以后：询问用户介入
    """
    
    # 用户介入后跳过循环检测的指令数量
    SKIP_AFTER_USER_INTERVENTION = 5
    
    def __init__(self, temperature_boost_levels: Optional[List[float]] = None):
        """初始化干预管理器
        
        Args:
            temperature_boost_levels: 温度提升级别列表
        """
        self.loop_count = 0
        self.temp_boost_levels = temperature_boost_levels or [0.3, 0.5, 0.7]
        self.last_intervention_iteration = 0
        self.skip_detection_count = 0  # 剩余需要跳过循环检测的指令数量
        
        logger.info("LoopInterventionManager initialized")
    
    def decide_intervention(
        self, 
        detection: "LoopDetectionResult",
        current_iteration: int
    ) -> Dict[str, Any]:
        """决定干预措施
        
        Args:
            detection: 循环检测结果
            current_iteration: 当前迭代次数
            
        Returns:
            dict: 干预措施配置
                - action: "boost_temperature" | "inject_reflection" | "ask_user"
                - temperature: 新的温度值（如果适用）
                - reflection_text: 反思提示文本（如果适用）
                - message: 日志消息
        """
        self.loop_count += 1
        self.last_intervention_iteration = current_iteration
        
        logger.info(f"Deciding intervention for loop #{self.loop_count} at iteration {current_iteration}")
        
        if self.loop_count == 1:
            # 第一次：提升温度
            new_temp = self.temp_boost_levels[0]
            return {
                "action": "boost_temperature",
                "temperature": new_temp,
                "message": f"🌡️  Loop detected (1st time), boosting temperature to {new_temp}"
            }
        
        elif self.loop_count == 2:
            # 第二次：注入反思 + 进一步提升温度
            reflection = self._build_reflection_prompt(detection)
            new_temp = self.temp_boost_levels[1] if len(self.temp_boost_levels) > 1 else 0.5
            return {
                "action": "inject_reflection",
                "reflection_text": reflection,
                "temperature": new_temp,
                "message": f"💭 Loop persists (2nd time), injecting reflection and boosting temperature to {new_temp}"
            }
        
        else:
            # 第三次及以后：询问用户
            new_temp = self.temp_boost_levels[2] if len(self.temp_boost_levels) > 2 else 0.7
            return {
                "action": "ask_user",
                "temperature": new_temp,
                "message": f"⚠️  Severe loop detected ({self.loop_count} times), requesting user intervention"
            }
    
    def reset(self):
        """重置干预计数器（用于新步骤）"""
        self.loop_count = 0
        self.last_intervention_iteration = 0
        self.skip_detection_count = 0
        logger.debug("LoopInterventionManager reset")
    
    def should_skip_detection(self) -> bool:
        """检查是否应该跳过循环检测
        
        Returns:
            bool: True 表示应该跳过检测
        """
        return self.skip_detection_count > 0
    
    def consume_skip_count(self):
        """消耗一次跳过计数（每次执行指令后调用）"""
        if self.skip_detection_count > 0:
            self.skip_detection_count -= 1
            logger.debug(f"Loop detection skip count decreased to {self.skip_detection_count}")
    
    def activate_user_intervention_mode(self):
        """激活用户介入模式，设置跳过检测的指令数量"""
        self.skip_detection_count = self.SKIP_AFTER_USER_INTERVENTION
        logger.info(f"👤 User intervention mode activated: skipping loop detection for next {self.SKIP_AFTER_USER_INTERVENTION} commands")

    
    def _build_reflection_prompt(self, detection: "LoopDetectionResult") -> str:
        """构建反思提示文本
        
        Args:
            detection: 循环检测结果
            
        Returns:
            str: 格式化的反思提示
        """
        evidence_str = "\n".join(f"  - {e}" for e in detection.evidence)
        
        loop_type_descriptions = {
            "direct_repeat": "repeating the same command without progress",
            "error_loop": "trying different commands but encountering the same error",
            "alternating": "alternating between commands without resolving the issue",
        }
        
        loop_desc = loop_type_descriptions.get(detection.loop_type, "executing in a loop")
        
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  LOOP DETECTED - REFLECTION REQUIRED ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analysis shows you are {loop_desc}:

{evidence_str}

Confidence: {detection.confidence:.1%}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MANDATORY REFLECTION - You MUST do the following:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **STOP and ANALYZE**: 
   - WHY did your previous attempts fail?
   - What assumption did you make that turned out to be wrong?
   - What information are you missing?

2. **CHANGE STRATEGY** - Your next action MUST be fundamentally different:
   ❌ NOT just adding flags like --force, --verbose, --ignore-errors
   ❌ NOT just repeating with sudo
   
   
   ✅ Consider: Different tool/approach
   ✅ Consider: Check system state first (logs, processes, files)
   ✅ Consider: Ask user for guidance or clarification
   ✅ Consider: Declare step_failed if truly stuck

3. **JUSTIFY YOUR NEW APPROACH**:
   - Explain specifically why THIS approach will work
   - What makes it different from previous attempts?
   - What evidence suggests it will succeed?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

If you genuinely cannot think of a fundamentally different approach,
you MUST declare "step_failed" rather than continue the loop.

Repeating the same pattern is NOT acceptable. Break the cycle NOW.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
