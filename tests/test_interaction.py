"""Tests for user interaction module."""

import pytest
from auto_deployer.interaction import (
    InteractionRequest,
    InteractionResponse,
    InputType,
    QuestionCategory,
    AutoResponseHandler,
    CLIInteractionHandler,
)


class TestInteractionRequest:
    """Tests for InteractionRequest dataclass."""

    def test_basic_choice_request(self):
        """Test creating a basic choice request."""
        request = InteractionRequest(
            question="Which port to use?",
            options=["3000", "5173", "8080"],
            input_type=InputType.CHOICE,
        )
        
        assert request.question == "Which port to use?"
        assert len(request.options) == 3
        assert request.input_type == InputType.CHOICE
        assert request.allow_custom is True

    def test_confirm_request(self):
        """Test creating a confirmation request."""
        request = InteractionRequest(
            question="Delete existing deployment?",
            input_type=InputType.CONFIRM,
            category=QuestionCategory.CONFIRMATION,
            default="n",
        )
        
        assert request.input_type == InputType.CONFIRM
        assert request.category == QuestionCategory.CONFIRMATION
        assert request.default == "n"

    def test_format_prompt_choice(self):
        """Test formatting prompt for choice input."""
        request = InteractionRequest(
            question="Select deployment mode:",
            options=["Development", "Production"],
            input_type=InputType.CHOICE,
            default="Development",
        )
        
        prompt = request.format_prompt()
        assert "Agent 需要您的输入" in prompt
        assert "Select deployment mode:" in prompt
        assert "[1] Development" in prompt
        assert "[2] Production" in prompt
        assert "(默认)" in prompt

    def test_format_prompt_confirm(self):
        """Test formatting prompt for confirm input."""
        request = InteractionRequest(
            question="Continue?",
            input_type=InputType.CONFIRM,
            category=QuestionCategory.CONFIRMATION,
        )
        
        prompt = request.format_prompt()
        assert "⚠️" in prompt  # Confirmation icon
        assert "[y/n]" in prompt


class TestInteractionResponse:
    """Tests for InteractionResponse dataclass."""

    def test_from_choice_valid(self):
        """Test creating response from valid choice."""
        options = ["Option A", "Option B", "Option C"]
        response = InteractionResponse.from_choice(2, options)
        
        assert response.value == "Option B"
        assert response.selected_option == 2
        assert response.is_custom is False

    def test_from_choice_custom(self):
        """Test creating response for custom input (option 0)."""
        options = ["Option A", "Option B"]
        response = InteractionResponse.from_choice(0, options)
        
        assert response.selected_option == 0
        assert response.is_custom is True

    def test_from_choice_invalid(self):
        """Test that invalid choice raises error."""
        options = ["Option A", "Option B"]
        
        with pytest.raises(ValueError):
            InteractionResponse.from_choice(5, options)

    def test_cancelled_response(self):
        """Test creating cancelled response."""
        response = InteractionResponse.cancelled_response()
        
        assert response.cancelled is True
        assert response.value == ""

    def test_timeout_response(self):
        """Test creating timeout response."""
        response = InteractionResponse.timeout_response()
        
        assert response.timed_out is True
        assert response.value == ""


class TestAutoResponseHandler:
    """Tests for AutoResponseHandler."""

    def test_auto_confirm_yes(self):
        """Test auto-confirming with yes."""
        handler = AutoResponseHandler(always_confirm=True)
        
        request = InteractionRequest(
            question="Proceed with deployment?",
            input_type=InputType.CONFIRM,
        )
        
        response = handler.ask(request)
        assert response.value == "yes"

    def test_auto_confirm_no(self):
        """Test auto-confirming with no."""
        handler = AutoResponseHandler(always_confirm=False)
        
        request = InteractionRequest(
            question="Delete files?",
            input_type=InputType.CONFIRM,
        )
        
        response = handler.ask(request)
        assert response.value == "no"

    def test_auto_choice_first_option(self):
        """Test auto-selecting first option."""
        handler = AutoResponseHandler()
        
        request = InteractionRequest(
            question="Select port:",
            options=["3000", "5173", "8080"],
            input_type=InputType.CHOICE,
        )
        
        response = handler.ask(request)
        assert response.value == "3000"
        assert response.selected_option == 1

    def test_auto_use_default(self):
        """Test using default value."""
        handler = AutoResponseHandler(use_defaults=True)
        
        request = InteractionRequest(
            question="Enter value:",
            input_type=InputType.TEXT,
            default="default_value",
        )
        
        response = handler.ask(request)
        assert response.value == "default_value"

    def test_predefined_responses(self):
        """Test using predefined responses based on keywords."""
        handler = AutoResponseHandler(
            default_responses={
                "port": "8080",
                "mode": "production",
            }
        )
        
        request = InteractionRequest(
            question="Which port should be used?",
            input_type=InputType.TEXT,
        )
        
        response = handler.ask(request)
        assert response.value == "8080"

    def test_notify(self):
        """Test notification (should not raise)."""
        handler = AutoResponseHandler()
        # Should not raise
        handler.notify("Test message", level="info")
        handler.notify("Warning message", level="warning")


class TestQuestionCategory:
    """Tests for question categories."""

    def test_all_categories_have_icons(self):
        """Ensure all categories get an icon in format_prompt."""
        categories = [
            QuestionCategory.DECISION,
            QuestionCategory.CONFIRMATION,
            QuestionCategory.INFORMATION,
            QuestionCategory.ERROR_RECOVERY,
            QuestionCategory.CUSTOM,
        ]
        
        for category in categories:
            request = InteractionRequest(
                question="Test question",
                category=category,
            )
            prompt = request.format_prompt()
            # Should have some emoji icon
            assert any(c for c in prompt if ord(c) > 127)  # Has non-ASCII (emoji)
