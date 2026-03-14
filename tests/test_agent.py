"""
Regression tests for agent.py

Tests verify that agent.py:
1. Runs successfully with a question
2. Outputs valid JSON
3. Has required fields: answer (non-empty string) and tool_calls (empty list)
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields."""
    # Path to agent.py
    agent_path = Path(__file__).parent.parent / "agent.py"

    # Run agent.py with a simple test question
    # Using a simple question that should get a quick response
    result = subprocess.run(
        ["uv", "run", str(agent_path), "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"agent.py failed with: {result.stderr}"

    # Parse stdout as JSON
    stdout = result.stdout.strip()
    assert stdout, "agent.py produced no output"

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"agent.py output is not valid JSON: {e}\nOutput: {stdout}")

    # Check required fields
    assert "answer" in data, "Missing 'answer' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Validate field types and values
    assert isinstance(data["answer"], str), "'answer' must be a string"
    assert len(data["answer"]) > 0, "'answer' must not be empty"
    assert isinstance(data["tool_calls"], list), "'tool_calls' must be a list"
    assert len(data["tool_calls"]) == 0, "'tool_calls' must be empty for Task 1"
