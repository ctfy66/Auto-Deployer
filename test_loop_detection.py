"""Test loop detection functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auto_deployer.orchestrator.loop_detector import LoopDetector
from auto_deployer.orchestrator.models import CommandRecord


def test_direct_repeat_detection():
    """Test detection of direct command repetition."""
    detector = LoopDetector(
        enabled=True,
        direct_repeat_threshold=3,
        command_similarity_threshold=0.85,
        output_similarity_threshold=0.80,
    )
    
    # Create repeated commands with similar output
    commands = [
        CommandRecord(
            command="npm install",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: EACCES permission denied",
            timestamp="2025-12-21T00:00:00"
        ),
        CommandRecord(
            command="npm install",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: EACCES permission denied",
            timestamp="2025-12-21T00:01:00"
        ),
        CommandRecord(
            command="npm install",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: EACCES permission denied",
            timestamp="2025-12-21T00:02:00"
        ),
    ]
    
    result = detector.check(commands)
    
    print(f"Loop detected: {result.is_loop}")
    print(f"Loop type: {result.loop_type}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Evidence:")
    for evidence in result.evidence:
        print(f"  - {evidence}")
    
    assert result.is_loop, "Should detect direct repeat loop"
    assert result.loop_type == "direct_repeat"
    assert result.confidence > 0.8


def test_error_loop_detection():
    """Test detection of error loop (different commands, same error)."""
    detector = LoopDetector(
        enabled=True,
        error_loop_threshold=4,
    )
    
    # Create different commands with same error
    commands = [
        CommandRecord(
            command="npm install express",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: EACCES permission denied /usr/local/lib/node_modules",
            timestamp="2025-12-21T00:00:00"
        ),
        CommandRecord(
            command="npm install --force express",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: EACCES permission denied /usr/local/lib/node_modules",
            timestamp="2025-12-21T00:01:00"
        ),
        CommandRecord(
            command="npm install --legacy-peer-deps express",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: EACCES permission denied /usr/local/lib/node_modules",
            timestamp="2025-12-21T00:02:00"
        ),
        CommandRecord(
            command="npm i express",
            success=False,
            exit_code=1,
            stdout="",
            stderr="Error: EACCES permission denied /usr/local/lib/node_modules",
            timestamp="2025-12-21T00:03:00"
        ),
    ]
    
    result = detector.check(commands)
    
    print(f"\nError loop detected: {result.is_loop}")
    print(f"Loop type: {result.loop_type}")
    print(f"Confidence: {result.confidence:.2%}")
    print(f"Evidence:")
    for evidence in result.evidence:
        print(f"  - {evidence}")
    
    assert result.is_loop, "Should detect error loop"
    assert result.loop_type == "error_loop"


def test_no_loop():
    """Test that normal progression is not flagged as loop."""
    detector = LoopDetector(enabled=True)
    
    # Different commands with different results (normal progress)
    commands = [
        CommandRecord(
            command="git clone https://github.com/user/repo",
            success=True,
            exit_code=0,
            stdout="Cloning into 'repo'...",
            stderr="",
            timestamp="2025-12-21T00:00:00"
        ),
        CommandRecord(
            command="cd repo",
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            timestamp="2025-12-21T00:01:00"
        ),
        CommandRecord(
            command="npm install",
            success=True,
            exit_code=0,
            stdout="added 100 packages",
            stderr="",
            timestamp="2025-12-21T00:02:00"
        ),
    ]
    
    result = detector.check(commands)
    
    print(f"\nNo loop detected: {not result.is_loop}")
    print(f"Loop type: {result.loop_type}")
    
    assert not result.is_loop, "Should not detect loop in normal progression"
    assert result.loop_type == "none"


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Loop Detection")
    print("=" * 60)
    
    test_direct_repeat_detection()
    print("\n✓ Direct repeat detection test passed")
    
    test_error_loop_detection()
    print("\n✓ Error loop detection test passed")
    
    test_no_loop()
    print("\n✓ No loop test passed")
    
    print("\n" + "=" * 60)
    print("All tests passed! 🎉")
    print("=" * 60)
