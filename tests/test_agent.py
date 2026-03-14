"""
Regression tests for agent.py

Tests verify that agent.py:
1. Outputs valid JSON with required fields (answer, source, tool_calls)
2. Uses correct tools for documentation questions
3. Returns proper source references
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str) -> tuple[int, str, str]:
    """
    Run agent.py with a question and return result.

    Args:
        question: The question to ask

    Returns:
        Tuple of (returncode, stdout, stderr)
    """
    agent_path = Path(__file__).parent.parent / "agent.py"
    result = subprocess.run(
        ["uv", "run", str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,  # Longer timeout for agentic loop
    )
    return result.returncode, result.stdout.strip(), result.stderr


def parse_json_output(stdout: str) -> dict:
    """Parse agent output as JSON."""
    assert stdout, "agent.py produced no output"
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AssertionError(f"agent.py output is not valid JSON: {e}\nOutput: {stdout}")


def test_agent_outputs_valid_json():
    """Test that agent.py outputs valid JSON with required fields."""
    returncode, stdout, stderr = run_agent("What is 2+2?")

    # Check exit code
    assert returncode == 0, f"agent.py failed with: {stderr}"

    # Parse and validate JSON
    data = parse_json_output(stdout)

    # Check required fields
    assert "answer" in data, "Missing 'answer' field in output"
    assert "source" in data, "Missing 'source' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Validate field types
    assert isinstance(data["answer"], str), "'answer' must be a string"
    assert len(data["answer"]) > 0, "'answer' must not be empty"
    assert isinstance(data["source"], str), "'source' must be a string"
    assert isinstance(data["tool_calls"], list), "'tool_calls' must be a list"


def test_merge_conflict_uses_read_file():
    """
    Test that asking about merge conflicts uses read_file tool.

    Expected behavior:
    - Agent should call list_files to find wiki files
    - Agent should call read_file to read git-workflow.md
    - Source should reference wiki/git-workflow.md
    """
    returncode, stdout, stderr = run_agent("How do you resolve a merge conflict?")

    # Check exit code
    assert returncode == 0, f"agent.py failed with: {stderr}"

    # Parse JSON
    data = parse_json_output(stdout)

    # Check required fields exist
    assert "answer" in data, "Missing 'answer' field"
    assert "source" in data, "Missing 'source' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Verify read_file was called
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "read_file" in tool_names, (
        f"Expected 'read_file' in tool_calls, got: {tool_names}"
    )

    # Verify source references git-workflow.md
    source = data["source"]
    assert "git-workflow.md" in source, (
        f"Expected 'git-workflow.md' in source, got: {source}"
    )

    # Verify answer is non-empty
    assert len(data["answer"]) > 0, "'answer' must not be empty"


def test_wiki_files_uses_list_files():
    """
    Test that asking about wiki files uses list_files tool.

    Expected behavior:
    - Agent should call list_files to list wiki directory
    - Tool result should contain file names
    """
    returncode, stdout, stderr = run_agent("What files are in the wiki?")

    # Check exit code
    assert returncode == 0, f"agent.py failed with: {stderr}"

    # Parse JSON
    data = parse_json_output(stdout)

    # Check required fields exist
    assert "answer" in data, "Missing 'answer' field"
    assert "source" in data, "Missing 'source' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Verify list_files was called
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "list_files" in tool_names, (
        f"Expected 'list_files' in tool_calls, got: {tool_names}"
    )

    # Verify list_files result contains expected files
    list_files_result = None
    for tc in data["tool_calls"]:
        if tc.get("tool") == "list_files":
            list_files_result = tc.get("result", "")
            break

    assert list_files_result is not None, "list_files result not found"
    # Check that result contains some expected wiki files
    assert "git-workflow.md" in list_files_result or "wiki" in list_files_result, (
        f"Expected wiki files in list_files result, got: {list_files_result}"
    )

    # Verify answer is non-empty
    assert len(data["answer"]) > 0, "'answer' must not be empty"


def test_framework_question_uses_read_file():
    """
    Test that asking about the backend framework uses read_file tool.

    Expected behavior:
    - Agent should call read_file to examine backend source code
    - Answer should mention FastAPI
    """
    returncode, stdout, stderr = run_agent("What Python web framework does this project's backend use?")

    # Check exit code
    assert returncode == 0, f"agent.py failed with: {stderr}"

    # Parse JSON
    data = parse_json_output(stdout)

    # Check required fields exist
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Verify read_file was called
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "read_file" in tool_names, (
        f"Expected 'read_file' in tool_calls, got: {tool_names}"
    )

    # Verify answer mentions FastAPI
    answer = data["answer"].lower()
    assert "fastapi" in answer, (
        f"Expected 'FastAPI' in answer, got: {data['answer']}"
    )


def test_item_count_question_uses_query_api():
    """
    Test that asking about item count uses query_api tool.

    Expected behavior:
    - Agent should call query_api to get item count from database
    - Answer should contain a number
    """
    returncode, stdout, stderr = run_agent("How many items are currently stored in the database?")

    # Check exit code
    assert returncode == 0, f"agent.py failed with: {stderr}"

    # Parse JSON
    data = parse_json_output(stdout)

    # Check required fields exist
    assert "answer" in data, "Missing 'answer' field"
    assert "tool_calls" in data, "Missing 'tool_calls' field"

    # Verify query_api was called
    tool_names = [tc.get("tool") for tc in data["tool_calls"]]
    assert "query_api" in tool_names, (
        f"Expected 'query_api' in tool_calls, got: {tool_names}"
    )

    # Verify answer contains a number
    import re
    answer = data["answer"]
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, (
        f"Expected a number in answer, got: {answer}"
    )
