"""Tests for the enhanced context management system.

Tests cover:
- ExecutionSummary creation and prompt context generation
- StepOutputs validation and parsing
- SummaryManager merge and truncation logic
"""

import pytest
from datetime import datetime

from src.auto_deployer.orchestrator.models import (
    ExecutionSummary,
    StepOutputs,
    StepContext,
    StepResult,
    StepStatus,
)
from src.auto_deployer.orchestrator.summary_manager import SummaryManager


class TestStepOutputs:
    """Tests for StepOutputs data class."""
    
    def test_create_minimal_outputs(self):
        """Test creating StepOutputs with only required fields."""
        outputs = StepOutputs(summary="Installed Node.js 18")
        
        assert outputs.summary == "Installed Node.js 18"
        assert outputs.environment_changes == {}
        assert outputs.new_configurations == {}
        assert outputs.artifacts == []
        assert outputs.services_started == []
        assert outputs.custom_data == {}
        assert outputs.issues_resolved == []
    
    def test_create_full_outputs(self):
        """Test creating StepOutputs with all fields."""
        outputs = StepOutputs(
            summary="Built and started the application",
            environment_changes={"node_version": "18.17.0", "pm2_installed": True},
            new_configurations={"NODE_ENV": "production", "PORT": "3000"},
            artifacts=["/home/user/app/dist/index.js"],
            services_started=[{"name": "myapp", "port": 3000, "pid": 12345}],
            custom_data={"build_hash": "abc123"},
            issues_resolved=[{"issue": "Port 3000 occupied", "resolution": "Changed to 3001"}],
        )
        
        assert outputs.summary == "Built and started the application"
        assert outputs.environment_changes["node_version"] == "18.17.0"
        assert outputs.new_configurations["PORT"] == "3000"
        assert len(outputs.artifacts) == 1
        assert outputs.services_started[0]["port"] == 3000
    
    def test_to_dict(self):
        """Test converting StepOutputs to dictionary."""
        outputs = StepOutputs(
            summary="Test summary",
            environment_changes={"key": "value"},
        )
        
        d = outputs.to_dict()
        assert d["summary"] == "Test summary"
        assert d["environment_changes"]["key"] == "value"
        assert "artifacts" in d
    
    def test_from_dict(self):
        """Test creating StepOutputs from dictionary."""
        data = {
            "summary": "From dict test",
            "environment_changes": {"test": True},
            "artifacts": ["/path/to/file"],
        }
        
        outputs = StepOutputs.from_dict(data)
        assert outputs.summary == "From dict test"
        assert outputs.environment_changes["test"] is True
        assert outputs.artifacts == ["/path/to/file"]
    
    def test_from_dict_with_missing_fields(self):
        """Test creating StepOutputs from incomplete dictionary."""
        data = {"summary": "Minimal"}
        
        outputs = StepOutputs.from_dict(data)
        assert outputs.summary == "Minimal"
        assert outputs.environment_changes == {}


class TestExecutionSummary:
    """Tests for ExecutionSummary data class."""
    
    def test_create_summary(self):
        """Test creating ExecutionSummary."""
        summary = ExecutionSummary(
            project_name="my-app",
            deploy_dir="/home/user/my-app",
            strategy="traditional",
        )
        
        assert summary.project_name == "my-app"
        assert summary.deploy_dir == "/home/user/my-app"
        assert summary.strategy == "traditional"
        assert summary.environment == {}
        assert summary.completed_actions == []
    
    def test_to_prompt_context_minimal(self):
        """Test generating prompt context with minimal data."""
        summary = ExecutionSummary(
            project_name="my-app",
            deploy_dir="/home/user/my-app",
            strategy="docker-compose",
        )
        
        context = summary.to_prompt_context()
        
        assert "my-app" in context
        assert "/home/user/my-app" in context
        assert "docker-compose" in context
    
    def test_to_prompt_context_with_data(self):
        """Test generating prompt context with full data."""
        summary = ExecutionSummary(
            project_name="my-app",
            deploy_dir="/home/user/my-app",
            strategy="traditional",
            environment={"node_version": "18.17.0", "pm2_installed": True},
            completed_actions=[
                "[PREREQUISITE] Install Node.js: Installed Node.js 18.17.0",
                "[SETUP] Clone repository: Cloned to ~/my-app",
            ],
            configurations={"NODE_ENV": "production"},
            resolved_issues=[{"issue": "Port conflict", "resolution": "Used port 3001"}],
        )
        
        context = summary.to_prompt_context()
        
        assert "node_version: 18.17.0" in context
        assert "Install Node.js" in context
        assert "NODE_ENV=production" in context
        assert "Port conflict" in context
    
    def test_to_prompt_context_truncation(self):
        """Test that prompt context respects truncation limits."""
        summary = ExecutionSummary(
            project_name="my-app",
            deploy_dir="/home/user/my-app",
            strategy="traditional",
            completed_actions=[f"Action {i}" for i in range(20)],
        )
        
        # Default max_actions is 10
        context = summary.to_prompt_context(max_actions=10)
        
        # Should mention that some actions were omitted
        assert "omitted" in context.lower() or "Action 19" in context


class TestSummaryManager:
    """Tests for SummaryManager class."""
    
    def test_initialization(self):
        """Test SummaryManager initialization."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="traditional",
        )
        
        summary = manager.get_summary()
        assert summary.project_name == "test-project"
        assert summary.deploy_dir == "/home/user/test-project"
        assert summary.strategy == "traditional"
        assert summary.last_updated != ""
    
    def test_merge_step_outputs(self):
        """Test merging step outputs into summary."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="traditional",
        )
        
        outputs = StepOutputs(
            summary="Installed Node.js 18.17.0",
            environment_changes={"node_version": "18.17.0"},
            new_configurations={"NODE_ENV": "production"},
            issues_resolved=[{"issue": "No Node.js", "resolution": "Installed via nvm"}],
        )
        
        manager.merge_step_outputs(
            step_name="Install Node.js",
            step_category="prerequisite",
            outputs=outputs,
        )
        
        summary = manager.get_summary()
        assert "node_version" in summary.environment
        assert summary.environment["node_version"] == "18.17.0"
        assert "NODE_ENV" in summary.configurations
        assert len(summary.completed_actions) == 1
        assert "Install Node.js" in summary.completed_actions[0]
        assert len(summary.resolved_issues) == 1
    
    def test_truncation(self):
        """Test that summary truncates old entries."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="traditional",
        )
        
        # Add more than MAX_COMPLETED_ACTIONS
        for i in range(20):
            outputs = StepOutputs(summary=f"Action {i}")
            manager.merge_step_outputs(
                step_name=f"Step {i}",
                step_category="setup",
                outputs=outputs,
            )
        
        summary = manager.get_summary()
        assert len(summary.completed_actions) <= SummaryManager.MAX_COMPLETED_ACTIONS
    
    def test_update_environment(self):
        """Test direct environment update."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="traditional",
        )
        
        manager.update_environment("custom_key", "custom_value")
        
        summary = manager.get_summary()
        assert summary.environment["custom_key"] == "custom_value"
    
    def test_update_configuration(self):
        """Test direct configuration update."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="traditional",
        )
        
        manager.update_configuration("MY_VAR", "my_value")
        
        summary = manager.get_summary()
        assert summary.configurations["MY_VAR"] == "my_value"
    
    def test_add_resolved_issue(self):
        """Test adding resolved issue."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="traditional",
        )
        
        manager.add_resolved_issue("Port 3000 in use", "Changed to port 3001")
        
        summary = manager.get_summary()
        assert len(summary.resolved_issues) == 1
        assert summary.resolved_issues[0]["issue"] == "Port 3000 in use"
        assert summary.resolved_issues[0]["resolution"] == "Changed to port 3001"
    
    def test_update_strategy(self):
        """Test updating deployment strategy."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="docker-compose",
        )
        
        manager.update_strategy("traditional")
        
        summary = manager.get_summary()
        assert summary.strategy == "traditional"
        # Should record the strategy change as a resolved issue
        assert any("Strategy change" in issue["issue"] for issue in summary.resolved_issues)
    
    def test_get_prompt_context(self):
        """Test getting prompt context string."""
        manager = SummaryManager(
            project_name="test-project",
            deploy_dir="/home/user/test-project",
            strategy="traditional",
        )
        
        manager.update_environment("node_version", "18.17.0")
        
        context = manager.get_prompt_context()
        
        assert "test-project" in context
        assert "node_version" in context


class TestStepResultWithStructuredOutputs:
    """Tests for StepResult with structured outputs."""
    
    def test_succeeded_with_structured_outputs(self):
        """Test creating successful result with structured outputs."""
        outputs = StepOutputs(summary="Task completed")
        result = StepResult.succeeded(
            outputs={"legacy": "data"},
            structured_outputs=outputs,
        )
        
        assert result.success is True
        assert result.status == StepStatus.SUCCESS
        assert result.outputs == {"legacy": "data"}
        assert result.structured_outputs is not None
        assert result.structured_outputs.summary == "Task completed"
    
    def test_succeeded_without_structured_outputs(self):
        """Test creating successful result without structured outputs (backward compat)."""
        result = StepResult.succeeded(outputs={"key": "value"})
        
        assert result.success is True
        assert result.outputs == {"key": "value"}
        assert result.structured_outputs is None


class TestStepContextWithSummary:
    """Tests for StepContext with execution summary."""
    
    def test_context_with_summary(self):
        """Test creating StepContext with execution summary."""
        summary = ExecutionSummary(
            project_name="my-app",
            deploy_dir="/home/user/my-app",
            strategy="traditional",
        )
        
        predecessor_outputs = {
            1: StepOutputs(summary="Previous step done"),
        }
        
        ctx = StepContext(
            step_id=2,
            step_name="Build",
            goal="Build the application",
            success_criteria="dist/ folder exists",
            category="build",
            execution_summary=summary,
            predecessor_outputs=predecessor_outputs,
        )
        
        assert ctx.execution_summary is not None
        assert ctx.execution_summary.project_name == "my-app"
        assert len(ctx.predecessor_outputs) == 1
        assert ctx.predecessor_outputs[1].summary == "Previous step done"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
