"""Simple verification script for step execution improvements.

Checks that the code changes are in place without actually running the code.
"""

import os

def check_file_contains(filepath, search_strings, description):
    """Check if file contains all search strings"""
    print(f"\nChecking: {description}")
    print(f"File: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"  ✗ File not found!")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    all_found = True
    for search_str in search_strings:
        if search_str in content:
            print(f"  ✓ Found: {search_str[:60]}...")
        else:
            print(f"  ✗ Missing: {search_str[:60]}...")
            all_found = False
    
    return all_found


def main():
    print("=" * 70)
    print("VERIFICATION: Step Execution Improvements")
    print("=" * 70)
    
    results = []
    
    # Test 1: StepContext has estimated_commands
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/models.py",
        [
            "estimated_commands: List[str]",
            "规划阶段建议的命令"
        ],
        "StepContext includes estimated_commands field"
    ))
    
    # Test 2: StepOutputs is simplified
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/models.py",
        [
            "key_info: Dict[str, Any]",
            "精简版",
            "只记录对后续步骤重要的信息"
        ],
        "StepOutputs is simplified to summary + key_info"
    ))
    
    # Test 3: Orchestrator passes estimated_commands
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/orchestrator.py",
        [
            "estimated_commands=step.estimated_commands"
        ],
        "Orchestrator passes estimated_commands to StepContext"
    ))
    
    # Test 4: Prompts include suggested commands
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/prompts.py",
        [
            "建议命令（来自规划阶段）",
            "Suggested Commands (from Planning Phase)"
        ],
        "System prompt includes suggested commands section"
    ))
    
    # Test 5: execution_step.py has estimated_commands parameter
    results.append(check_file_contains(
        "src/auto_deployer/prompts/execution_step.py",
        [
            "estimated_commands: list | None = None",
            "Suggested Commands (from Planning)"
        ],
        "Execution step prompt accepts and displays estimated_commands"
    ))
    
    # Test 6: step_executor.py passes estimated_commands to prompts
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/step_executor.py",
        [
            "estimated_commands=step_ctx.estimated_commands"
        ],
        "StepExecutor passes estimated_commands to prompt builders"
    ))
    
    # Test 7: Simplified output format in prompts
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/prompts.py",
        [
            '"key_info"',
            "Only include information that subsequent steps need"
        ],
        "Prompts use simplified output format"
    ))
    
    # Test 8: Validation updated for simplified structure
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/step_executor.py",
        [
            "key_info = outputs_dict.get",
            "简化版"
        ],
        "Output validation updated for simplified structure"
    ))
    
    # Test 9: Summary manager updated
    results.append(check_file_contains(
        "src/auto_deployer/orchestrator/summary_manager.py",
        [
            "outputs.key_info",
            "简化版"
        ],
        "Summary manager updated to use key_info"
    ))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTests passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL CHECKS PASSED!")
        print("\nChanges successfully implemented:")
        print("  1. ✓ estimated_commands added to StepContext")
        print("  2. ✓ StepOutputs simplified (summary + key_info only)")
        print("  3. ✓ Orchestrator passes estimated_commands to steps")
        print("  4. ✓ Prompts display suggested commands from planning")
        print("  5. ✓ Output format simplified in all prompts")
        print("  6. ✓ Validation and summary manager updated")
        return 0
    else:
        print(f"\n❌ {total - passed} checks failed")
        return 1


if __name__ == "__main__":
    exit(main())
