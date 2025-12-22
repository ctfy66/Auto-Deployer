"""Quick test for prompts refactor."""

def test_imports():
    """Test that all prompts can be imported."""
    from src.auto_deployer.prompts import (
        build_planning_prompt,
        build_step_execution_prompt,
        build_step_execution_prompt_windows,
        build_agent_prompt,
        STEP_EXECUTION_PROMPT,
        STEP_EXECUTION_PROMPT_WINDOWS,
    )
    print("[PASS] All imports successful")


def test_planning_prompt():
    """Test planning prompt generation."""
    from src.auto_deployer.prompts import build_planning_prompt, build_host_details_local

    host_details = build_host_details_local(
        os_name="Linux",
        os_release="Ubuntu 22.04",
        architecture="x86_64",
        kernel="5.15.0",
        is_container=False,
        has_systemd=True,
        available_tools={"docker": True, "git": True, "node": True},
    )

    prompt = build_planning_prompt(
        repo_url="https://github.com/test/repo",
        deploy_dir="/home/user/app",
        project_type="nodejs",
        framework="express",
        repo_analysis="Project uses Express.js framework",
        target_info="Local machine (Linux)",
        host_details=host_details,
    )

    assert "nodejs" in prompt
    assert "express" in prompt
    assert "deployment plan" in prompt.lower()
    print("[PASS] Planning prompt generation works")


def test_step_execution_prompt():
    """Test step execution prompt generation."""
    from src.auto_deployer.prompts import build_step_execution_prompt

    prompt = build_step_execution_prompt(
        step_id=1,
        step_name="Install dependencies",
        category="setup",
        goal="Install Node.js dependencies",
        success_criteria="node_modules directory exists",
        repo_url="https://github.com/test/repo",
        deploy_dir="/home/user/app",
        host_info="Ubuntu 22.04",
        commands_history="(no commands executed yet)",
        user_interactions="(no user interactions)",
        max_iterations=10,
        current_iteration=1,
        os_type="linux",
    )

    assert "Install dependencies" in prompt
    assert "node_modules" in prompt
    assert "step_done" in prompt
    print("[PASS] Step execution prompt generation works")


def test_legacy_constants():
    """Test backward compatibility with legacy constants."""
    from src.auto_deployer.prompts import (
        STEP_EXECUTION_PROMPT,
        STEP_EXECUTION_PROMPT_WINDOWS,
    )

    # These should be string templates
    assert "{step_id}" in STEP_EXECUTION_PROMPT
    assert "{step_name}" in STEP_EXECUTION_PROMPT
    assert "PowerShell" in STEP_EXECUTION_PROMPT_WINDOWS
    print("[PASS] Legacy constants available for backward compatibility")


if __name__ == "__main__":
    test_imports()
    test_planning_prompt()
    test_step_execution_prompt()
    test_legacy_constants()
    print("\nAll tests passed!")
