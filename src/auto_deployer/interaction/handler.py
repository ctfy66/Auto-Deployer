"""User interaction handler for Agent communication."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)


class InputType(str, Enum):
    """Type of user input expected."""
    CHOICE = "choice"       # 选择题，从options中选择
    TEXT = "text"           # 自由文本输入
    CONFIRM = "confirm"     # 是/否确认
    SECRET = "secret"       # 敏感信息（密码等）


class QuestionCategory(str, Enum):
    """Category of questions for context."""
    DECISION = "decision"           # 部署决策（选择端口、入口点等）
    CONFIRMATION = "confirmation"   # 确认高风险操作
    INFORMATION = "information"     # 需要额外信息（环境变量等）
    ERROR_RECOVERY = "error_recovery"  # 错误恢复选项
    CUSTOM = "custom"               # 自定义问题


@dataclass
class InteractionRequest:
    """A request from Agent to user for input."""
    
    question: str                               # 主要问题
    input_type: InputType = InputType.CHOICE    # 输入类型
    options: List[str] = field(default_factory=list)  # 可选项（用于 CHOICE 类型）
    category: QuestionCategory = QuestionCategory.DECISION
    context: Optional[str] = None               # 附加上下文信息
    default: Optional[str] = None               # 默认选项
    allow_custom: bool = True                   # 是否允许自定义输入（用于 CHOICE 类型）
    timeout: Optional[int] = None               # 超时时间（秒），None 表示无限等待
    
    def format_prompt(self) -> str:
        """Format the request as a user-friendly prompt."""
        lines = []
        
        # 分类图标
        icons = {
            QuestionCategory.DECISION: "🤔",
            QuestionCategory.CONFIRMATION: "⚠️",
            QuestionCategory.INFORMATION: "📝",
            QuestionCategory.ERROR_RECOVERY: "🔧",
            QuestionCategory.CUSTOM: "💬",
        }
        icon = icons.get(self.category, "❓")
        
        lines.append(f"\n{icon} Agent 需要您的输入:")
        lines.append(f"   {self.question}")
        
        if self.context:
            lines.append(f"\n   ℹ️  {self.context}")
        
        if self.input_type == InputType.CHOICE and self.options:
            lines.append("\n   选项:")
            for i, option in enumerate(self.options, 1):
                default_marker = " (默认)" if self.default == option else ""
                lines.append(f"   [{i}] {option}{default_marker}")
            if self.allow_custom:
                lines.append(f"   [0] 自定义输入 (您可以输入自己的指令或值)")
                lines.append(f"   💡 提示: 您也可以直接输入文本作为自定义值")
        
        elif self.input_type == InputType.CONFIRM:
            default_hint = ""
            if self.default:
                default_hint = f" (默认: {self.default})"
            lines.append(f"\n   请输入 [y/n]{default_hint}:")
        
        elif self.input_type == InputType.TEXT:
            if self.default:
                lines.append(f"\n   (默认: {self.default})")
        
        elif self.input_type == InputType.SECRET:
            lines.append("\n   (输入将被隐藏)")
        
        return "\n".join(lines)


@dataclass
class InteractionResponse:
    """User's response to an interaction request."""
    
    value: str                      # 用户输入的值
    selected_option: Optional[int] = None  # 选择的选项索引（1-based），0 表示自定义
    is_custom: bool = False         # 是否是自定义输入
    cancelled: bool = False         # 用户是否取消了
    timed_out: bool = False         # 是否超时
    metadata: Optional[dict] = None # 用于存储额外的元数据（如 auto_retry 信息）
    
    @classmethod
    def from_choice(cls, option_index: int, options: List[str]) -> "InteractionResponse":
        """Create response from a choice selection."""
        if option_index == 0:
            return cls(value="", selected_option=0, is_custom=True)
        if 1 <= option_index <= len(options):
            return cls(value=options[option_index - 1], selected_option=option_index)
        raise ValueError(f"Invalid option index: {option_index}")
    
    @classmethod
    def cancelled_response(cls) -> "InteractionResponse":
        """Create a cancelled response."""
        return cls(value="", cancelled=True)
    
    @classmethod
    def timeout_response(cls) -> "InteractionResponse":
        """Create a timeout response."""
        return cls(value="", timed_out=True)


class UserInteractionHandler(ABC):
    """Abstract base class for handling user interactions."""
    
    @abstractmethod
    def ask(self, request: InteractionRequest) -> InteractionResponse:
        """
        Present a request to the user and get their response.
        
        Args:
            request: The interaction request to present
            
        Returns:
            The user's response
        """
        pass
    
    @abstractmethod
    def notify(self, message: str, level: str = "info") -> None:
        """
        Send a notification to the user (no response needed).
        
        Args:
            message: The message to display
            level: Severity level (info, warning, error)
        """
        pass


class CLIInteractionHandler(UserInteractionHandler):
    """Command-line interface interaction handler."""
    
    def __init__(self, use_rich: bool = True) -> None:
        """
        Initialize the CLI handler.
        
        Args:
            use_rich: Whether to use rich library for better formatting
        """
        self.use_rich = use_rich
        self._rich_console = None
        
        if use_rich:
            try:
                from rich.console import Console
                from rich.prompt import Prompt, Confirm
                self._rich_console = Console()
            except ImportError:
                self.use_rich = False
                logger.debug("rich library not available, using basic CLI")
    
    def ask(self, request: InteractionRequest) -> InteractionResponse:
        """Present request and get user input via CLI."""
        print(request.format_prompt())
        
        try:
            if request.input_type == InputType.CHOICE:
                return self._handle_choice(request)
            elif request.input_type == InputType.CONFIRM:
                return self._handle_confirm(request)
            elif request.input_type == InputType.SECRET:
                return self._handle_secret(request)
            else:  # TEXT
                return self._handle_text(request)
        except KeyboardInterrupt:
            print("\n   (已取消)")
            return InteractionResponse.cancelled_response()
        except EOFError:
            return InteractionResponse.cancelled_response()
    
    def _handle_choice(self, request: InteractionRequest) -> InteractionResponse:
        """Handle choice input."""
        while True:
            prompt = "\n   请选择"
            if request.default:
                try:
                    default_idx = request.options.index(request.default) + 1
                    prompt += f" [{default_idx}]"
                except ValueError:
                    pass
            prompt += ": "
            
            user_input = input(prompt).strip()
            
            # 使用默认值
            if not user_input and request.default:
                try:
                    idx = request.options.index(request.default) + 1
                    return InteractionResponse.from_choice(idx, request.options)
                except ValueError:
                    return InteractionResponse(value=request.default)
            
            # 解析选项编号
            try:
                choice = int(user_input)
                if choice == 0 and request.allow_custom:
                    # 自定义输入
                    custom_value = input("   💬 请输入自定义值 (例如命令、配置值等): ").strip()
                    if not custom_value:
                        print("   ⚠️  自定义值不能为空，请重新输入")
                        continue
                    return InteractionResponse(value=custom_value, selected_option=0, is_custom=True)
                elif 1 <= choice <= len(request.options):
                    return InteractionResponse.from_choice(choice, request.options)
                else:
                    if request.allow_custom:
                        print(f"   ❌ 无效选项，请输入 0-{len(request.options)} 或直接输入文本")
                    else:
                        print(f"   ❌ 无效选项，请输入 1-{len(request.options)}")
            except ValueError:
                # 直接输入文本作为自定义值
                if request.allow_custom:
                    print(f"   ✅ 已接收自定义输入: {user_input}")
                    return InteractionResponse(value=user_input, is_custom=True)
                print("   ❌ 请输入有效的选项编号")
    
    def _handle_confirm(self, request: InteractionRequest) -> InteractionResponse:
        """Handle yes/no confirmation."""
        default = request.default or "n"
        
        while True:
            prompt = f"\n   确认? [y/n] (默认: {default}): "
            user_input = input(prompt).strip().lower()
            
            if not user_input:
                user_input = default
            
            if user_input in ("y", "yes", "是"):
                return InteractionResponse(value="yes")
            elif user_input in ("n", "no", "否"):
                return InteractionResponse(value="no")
            else:
                print("   ❌ 请输入 y 或 n")
    
    def _handle_text(self, request: InteractionRequest) -> InteractionResponse:
        """Handle free text input."""
        prompt = "\n   请输入"
        if request.default:
            prompt += f" (默认: {request.default})"
        prompt += ": "
        
        user_input = input(prompt).strip()
        if not user_input and request.default:
            user_input = request.default
        
        return InteractionResponse(value=user_input)
    
    def _handle_secret(self, request: InteractionRequest) -> InteractionResponse:
        """Handle secret/password input."""
        import getpass
        
        prompt = "\n   请输入 (不显示): "
        try:
            user_input = getpass.getpass(prompt)
            return InteractionResponse(value=user_input)
        except Exception:
            # Fallback to regular input
            print("   (警告: 输入可能可见)")
            user_input = input(prompt).strip()
            return InteractionResponse(value=user_input)
    
    def notify(self, message: str, level: str = "info") -> None:
        """Display a notification message."""
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        icon = icons.get(level, "•")
        print(f"\n{icon} {message}")


class CallbackInteractionHandler(UserInteractionHandler):
    """
    Interaction handler that uses callbacks.
    Useful for GUI or web interfaces.
    """
    
    def __init__(
        self,
        ask_callback: Callable[[InteractionRequest], InteractionResponse],
        notify_callback: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """
        Initialize with callbacks.
        
        Args:
            ask_callback: Function to call when asking user for input
            notify_callback: Function to call for notifications
        """
        self.ask_callback = ask_callback
        self.notify_callback = notify_callback or (lambda msg, lvl: print(f"[{lvl}] {msg}"))
    
    def ask(self, request: InteractionRequest) -> InteractionResponse:
        return self.ask_callback(request)
    
    def notify(self, message: str, level: str = "info") -> None:
        self.notify_callback(message, level)


class AutoResponseHandler(UserInteractionHandler):
    """
    Automatic response handler for testing or non-interactive mode.
    Always uses default values or predefined responses.
    """
    
    def __init__(
        self,
        default_responses: Optional[dict] = None,
        always_confirm: bool = True,
        use_defaults: bool = True,
    ) -> None:
        """
        Initialize auto-response handler.
        
        Args:
            default_responses: Dict mapping question keywords to responses
            always_confirm: Whether to auto-confirm (True) or reject (False)
            use_defaults: Whether to use default values when available
        """
        self.default_responses = default_responses or {}
        self.always_confirm = always_confirm
        self.use_defaults = use_defaults
    
    def ask(self, request: InteractionRequest) -> InteractionResponse:
        logger.info(f"Auto-responding to: {request.question[:50]}...")
        
        # Check for predefined response
        for keyword, response in self.default_responses.items():
            if keyword.lower() in request.question.lower():
                return InteractionResponse(value=response)
        
        # Use default if available
        if self.use_defaults and request.default:
            return InteractionResponse(value=request.default)
        
        # Handle by type
        if request.input_type == InputType.CONFIRM:
            return InteractionResponse(value="yes" if self.always_confirm else "no")
        elif request.input_type == InputType.CHOICE and request.options:
            # 选择第一个选项
            return InteractionResponse.from_choice(1, request.options)
        else:
            return InteractionResponse(value="")
    
    def notify(self, message: str, level: str = "info") -> None:
        logger.info(f"[{level}] {message}")


class AutoRetryHandler(UserInteractionHandler):
    """
    Auto-retry handler for non-interactive mode.
    When asked for input, returns a 'retry' signal to trigger replanning.
    """
    
    def __init__(self, retry_message: str = "retry") -> None:
        """
        Initialize auto-retry handler.
        
        Args:
            retry_message: The message to return when interaction is needed
        """
        self.retry_message = retry_message
        logger.info("🤖 Using AutoRetryHandler - will trigger replanning on user interactions")
    
    def ask(self, request: InteractionRequest) -> InteractionResponse:
        """Return retry signal instead of asking user."""
        logger.info(f"[AUTO MODE] 🔄 Interaction requested: {request.question[:80]}")
        logger.info(f"[AUTO MODE] 🔄 Returning '{self.retry_message}' to trigger replanning")
        
        # 返回特殊的 retry 响应
        return InteractionResponse(
            value=self.retry_message,
            is_custom=True,
            metadata={"auto_retry": True, "original_question": request.question}
        )
    
    def notify(self, message: str, level: str = "info") -> None:
        """Log notifications."""
        logger.info(f"[AUTO MODE - {level.upper()}] {message}")
