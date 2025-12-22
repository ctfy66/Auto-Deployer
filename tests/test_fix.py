#!/usr/bin/env python3
"""Test the fix for build_planning_prompt function."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock the required modules for testing
class MockModule:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None

sys.modules['dotenv'] = MockModule()
sys.modules['auto_deployer.config'] = MockModule()

# Import the function we fixed
from auto_deployer.prompts.planning import build_planning_prompt

# Test data
test_data = {
    "repo_url": "https://github.com/example/test",
    "deploy_dir": "/tmp/test",
    "project_type": "python",
    "framework": "flask",
    "repo_analysis": "Found Flask app with requirements.txt",
    "target_info": "Local machine",
    "host_details": "# Host Details\n{\"os\": \"linux\"}"
}

# Test the function
try:
    prompt = build_planning_prompt(**test_data)
    print("[OK] build_planning_prompt() works correctly!")
    print(f"Generated prompt length: {len(prompt)} characters")

    # Check if key components are in the prompt
    required_components = [
        "Repository: https://github.com/example/test",
        "Deploy Directory: /tmp/test",
        "Project Type: python",
        "Framework: flask",
        "Flask app with requirements.txt"
    ]

    missing = []
    for comp in required_components:
        if comp not in prompt:
            missing.append(comp)

    if missing:
        print(f"[WARNING] Missing components: {missing}")
    else:
        print("[OK] All required components present in prompt")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()