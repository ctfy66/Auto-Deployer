#!/usr/bin/env python3
"""Test script to compare prompt complexity before and after simplification."""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from auto_deployer.prompts.execution_step import (
    build_simplified_step_prompt,
    build_step_execution_prompt,
    build_step_execution_prompt_windows,
)

# Test data
test_params = {
    "step_id": 1,
    "step_name": "Install Dependencies",
    "category": "setup",
    "goal": "Install project dependencies using npm",
    "success_criteria": "node_modules directory exists and npm install completes without errors",
    "repo_url": "https://github.com/example/node-app.git",
    "deploy_dir": "/home/user/app",
    "host_info": '{"os": "linux", "python": "3.9", "node": "16"}',
    "commands_history": "No commands executed yet.",
    "user_interactions": "No user interactions yet.",
    "max_iterations": 10,
    "current_iteration": 1,
    "os_type": "linux"
}

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens in text using rough estimation."""
    # Rough estimation: 1 token ≈ 4 characters for English
    # For mixed content with code, we'll use 1 token ≈ 3.5 characters
    return int(len(text) / 3.5)

def test_prompt_complexity():
    """Test and compare prompt complexities."""

    print("=" * 70)
    print("Prompt Complexity Comparison")
    print("=" * 70)

    # Test simplified prompt
    simplified_prompt = build_simplified_step_prompt(**test_params)
    simplified_tokens = count_tokens(simplified_prompt)

    # Test original prompt (Linux)
    original_prompt = build_step_execution_prompt(**test_params)
    original_tokens = count_tokens(original_prompt)

    # Test original prompt (Windows)
    test_params_windows = test_params.copy()
    test_params_windows["os_type"] = "windows"
    windows_prompt = build_step_execution_prompt_windows(**test_params_windows)
    windows_tokens = count_tokens(windows_prompt)

    # Print results
    print(f"\n1. Simplified Prompt (Linux):")
    print(f"   Tokens: {simplified_tokens:,}")
    print(f"   Characters: {len(simplified_prompt):,}")

    print(f"\n2. Original Prompt (Linux):")
    print(f"   Tokens: {original_tokens:,}")
    print(f"   Characters: {len(original_prompt):,}")

    print(f"\n3. Original Prompt (Windows):")
    print(f"   Tokens: {windows_tokens:,}")
    print(f"   Characters: {len(windows_prompt):,}")

    # Calculate improvements
    linux_reduction = (original_tokens - simplified_tokens) / original_tokens * 100
    windows_reduction = (windows_tokens - simplified_tokens) / windows_tokens * 100

    print("\n" + "=" * 70)
    print("Improvement Summary")
    print("=" * 70)
    print(f"\nLinux prompt reduction: {linux_reduction:.1f}% ({original_tokens - simplified_tokens:,} fewer tokens)")
    print(f"Windows prompt reduction: {windows_reduction:.1f}% ({windows_tokens - simplified_tokens:,} fewer tokens)")

    # Show sample of simplified prompt
    print("\n" + "=" * 70)
    print("Sample Simplified Prompt (first 500 chars):")
    print("=" * 70)
    print(simplified_prompt[:500] + "..." if len(simplified_prompt) > 500 else simplified_prompt)

    # Cost analysis (assuming GPT-4 pricing)
    cost_per_1k_input = 0.03  # USD
    cost_per_1k_output = 0.06

    print("\n" + "=" * 70)
    print("Cost Analysis (per 1000 steps)")
    print("=" * 70)
    print(f"Original Linux: ${original_tokens/1000 * cost_per_1k_input * 1000:.2f}")
    print(f"Simplified: ${simplified_tokens/1000 * cost_per_1k_input * 1000:.2f}")
    print(f"Savings: ${(original_tokens - simplified_tokens)/1000 * cost_per_1k_input * 1000:.2f}")

    return {
        "simplified_tokens": simplified_tokens,
        "original_linux_tokens": original_tokens,
        "original_windows_tokens": windows_tokens,
        "linux_reduction_percent": linux_reduction,
        "windows_reduction_percent": windows_reduction
    }

if __name__ == "__main__":
    results = test_prompt_complexity()
    print("\n✅ Prompt simplification analysis complete!")