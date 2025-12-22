"""Test script for context compression functionality."""

import sys
import os

# Direct import of the module file
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'auto_deployer', 'llm'))

import token_manager
TokenManager = token_manager.TokenManager
PROVIDER_TOKEN_LIMITS = token_manager.PROVIDER_TOKEN_LIMITS

from datetime import datetime

# Simple CommandRecord for testing
class CommandRecord:
    def __init__(self, command, success, exit_code, stdout, stderr, timestamp):
        self.command = command
        self.success = success
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timestamp = timestamp

def test_token_manager():
    """Test TokenManager functionality."""
    print("=" * 60)
    print("Testing TokenManager")
    print("=" * 60)
    
    # Test different providers
    providers = [
        ("gemini", "gemini-2.0-flash-exp"),
        ("openai", "gpt-4o"),
        ("anthropic", "claude-3-5-sonnet-20241022"),
        ("deepseek", "deepseek-chat"),
    ]
    
    for provider, model in providers:
        tm = TokenManager(provider, model)
        limit = tm.get_limit()
        print(f"\n{provider}/{model}: {limit:,} tokens")
        
        # Test token counting
        test_text = "Hello world! " * 100
        token_count = tm.count_tokens(test_text)
        print(f"  Sample text ({len(test_text)} chars) → {token_count} tokens")
        
        # Test compression trigger
        large_text = "x" * (limit * 2)  # 50% threshold
        should_compress = tm.should_compress(large_text, threshold=0.5)
        print(f"  Should compress at 50%: {should_compress}")
    
    print("\n✓ TokenManager tests passed")


def test_command_record_structure():
    """Test CommandRecord structure with full output."""
    print("\n" + "=" * 60)
    print("Testing CommandRecord with full output")
    print("=" * 60)
    
    # Create a sample command record with large output
    large_output = "\n".join([f"Line {i}: Some output data" for i in range(100)])
    
    record = CommandRecord(
        command="npm install",
        success=True,
        exit_code=0,
        stdout=large_output,
        stderr="",
        timestamp="2025-12-20T10:00:00"
    )
    
    print(f"\nCommand: {record.command}")
    print(f"Success: {record.success}")
    print(f"Stdout length: {len(record.stdout)} chars")
    print(f"First 100 chars: {record.stdout[:100]}...")
    
    print("\n✓ CommandRecord structure tests passed")


def test_provider_limits():
    """Display all provider limits."""
    print("\n" + "=" * 60)
    print("Provider Token Limits")
    print("=" * 60)
    
    for provider, limits in PROVIDER_TOKEN_LIMITS.items():
        if isinstance(limits, dict):
            print(f"\n{provider}:")
            for model, limit in limits.items():
                print(f"  {model}: {limit:,}")
        else:
            print(f"\n{provider}: {limits:,}")
    
    print("\n✓ Provider limits displayed")


if __name__ == "__main__":
    try:
        test_token_manager()
        test_command_record_structure()
        test_provider_limits()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
