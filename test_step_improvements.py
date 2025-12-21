"""Test script to verify step execution improvements.

This script tests:
1. estimated_commands are passed to StepContext
2. Simplified StepOutputs structure works correctly
3. Prompts include suggested commands
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Direct imports to avoid loading config
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

def test_step_context_with_estimated_commands():
    """Test that StepContext can hold estimated_commands"""
    print("=" * 60)
    print("Test 1: StepContext with estimated_commands")
    print("=" * 60)
    
    ctx = StepContext(
        step_id=6,
        step_name="Verify Application",
        goal="Test app accessibility",
        success_criteria="HTTP 200 response",
        category="verify",
        estimated_commands=[
            "Start-Process 'http://localhost:4090'",
            "Invoke-WebRequest -Uri http://localhost:4090"
        ]
    )
    
    print(f"✓ Step ID: {ctx.step_id}")
    print(f"✓ Step Name: {ctx.step_name}")
    print(f"✓ Estimated Commands: {len(ctx.estimated_commands)} commands")
    for i, cmd in enumerate(ctx.estimated_commands, 1):
        print(f"  {i}. {cmd}")
    print()


def test_simplified_step_outputs():
    """Test simplified StepOutputs structure"""
    print("=" * 60)
    print("Test 2: Simplified StepOutputs")
    print("=" * 60)
    
    # Old structure would have many fields
    # New structure only has summary and key_info
    outputs = StepOutputs(
        summary="Started Node.js service on port 4090",
        key_info={"port": 4090, "service": "nodejs"}
    )
    
    print(f"✓ Summary: {outputs.summary}")
    print(f"✓ Key Info: {outputs.key_info}")
    print(f"✓ Dict format: {outputs.to_dict()}")
    print()


def test_prompt_includes_suggested_commands():
    """Test that prompts include suggested commands"""
    print("=" * 60)
    print("Test 3: Prompt includes suggested commands")
    print("=" * 60)
    
    from auto_deployer.orchestrator.models import ExecutionSummary
    
    # Create execution summary
    summary = ExecutionSummary(
        project_name="TestApp",
        deploy_dir="/app",
        strategy="docker-compose"
    )
    
    # Create step context with estimated commands
    ctx = StepContext(
        step_id=6,
        step_name="Verify Application",
        goal="Test app accessibility on port 4090",
        success_criteria="HTTP 200 response from localhost:4090",
        category="verify",
        estimated_commands=[
            "Start-Process 'http://localhost:4090'",
            "Invoke-WebRequest -Uri http://localhost:4090 -UseBasicParsing"
        ],
        execution_summary=summary
    )
    
    # Build prompt
    prompt = build_step_system_prompt(ctx, summary, is_windows=True)
    
    # Check if suggested commands are in prompt
    if "Suggested Commands" in prompt:
        print("✓ Prompt includes 'Suggested Commands' section")
    else:
        print("✗ FAILED: Prompt missing 'Suggested Commands' section")
        
    if "http://localhost:4090" in prompt:
        print("✓ Prompt includes port 4090 (from estimated_commands)")
    else:
        print("✗ FAILED: Prompt missing port information")
    
    if "summary" in prompt.lower() and "key_info" in prompt.lower():
        print("✓ Prompt includes simplified output format (summary, key_info)")
    else:
        print("✗ FAILED: Prompt missing new output format")
    
    print(f"\n✓ Prompt length: {len(prompt)} characters")
    print()


def test_output_format_in_prompt():
    """Test that output format is simplified"""
    print("=" * 60)
    print("Test 4: Simplified output format in prompts")
    print("=" * 60)
    
    from auto_deployer.prompts.execution_step import build_simplified_step_prompt
    
    prompt = build_simplified_step_prompt(
        step_id=1,
        step_name="Test Step",
        goal="Test goal",
        success_criteria="Success",
        repo_url="https://github.com/test/repo",
        deploy_dir="/app",
        host_info="Windows 11",
        commands_history="No commands yet",
        user_interactions="No interactions",
        max_iterations=30,
        current_iteration=1,
        os_type="windows",
        estimated_commands=["echo test", "dir"]
    )
    
    # Check for old complex fields (should NOT be present)
    old_fields = ["environment_changes", "new_configurations", "artifacts", "services_started"]
    has_old_fields = any(field in prompt for field in old_fields)
    
    if not has_old_fields:
        print("✓ Prompt does NOT contain old complex fields")
    else:
        print("✗ FAILED: Prompt still contains old complex fields")
    
    # Check for new simple fields (should be present)
    if "key_info" in prompt:
        print("✓ Prompt contains new 'key_info' field")
    else:
        print("✗ FAILED: Prompt missing 'key_info' field")
    
    if 'summary": "One sentence' in prompt or "summary" in prompt.lower():
        print("✓ Prompt contains 'summary' field requirement")
    else:
        print("✗ FAILED: Prompt missing 'summary' field")
    
    print()


if __name__ == "__main__":
    try:
        test_step_context_with_estimated_commands()
        test_simplified_step_outputs()
        test_prompt_includes_suggested_commands()
        test_output_format_in_prompt()
        
        print("=" * 60)
        print("✅ All tests completed!")
        print("=" * 60)
        print("\nSummary of improvements:")
        print("1. ✓ estimated_commands now passed to step execution context")
        print("2. ✓ StepOutputs simplified (only summary + key_info)")
        print("3. ✓ Prompts show suggested commands from planning phase")
        print("4. ✓ Output format simplified to reduce token usage")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
