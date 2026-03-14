#!/usr/bin/env python3
"""
LLM Agent CLI - Task 2: Documentation Agent

An agent that uses tools (read_file, list_files) to navigate the project wiki
and answer questions with proper source references.

Usage:
    uv run agent.py "Your question here"

Output:
    {
      "answer": "...",
      "source": "wiki/file.md#section",
      "tool_calls": [...]
    }
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Maximum tool calls per question
MAX_TOOL_CALLS = 10

# Project root directory (parent of agent.py)
PROJECT_ROOT = Path(__file__).parent.resolve()


def load_env() -> None:
    """Load environment variables from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        sys.exit(1)
    load_dotenv(env_file)


def get_llm_config() -> dict:
    """Get LLM configuration from environment variables."""
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not api_key:
        print("Error: LLM_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    if not api_base:
        print("Error: LLM_API_BASE not set", file=sys.stderr)
        sys.exit(1)
    if not model:
        print("Error: LLM_MODEL not set", file=sys.stderr)
        sys.exit(1)

    return {
        "api_key": api_key,
        "api_base": api_base,
        "model": model,
    }


def safe_path(base: Path, relative: str) -> Path | None:
    """
    Resolve a path and ensure it stays within the base directory.

    Args:
        base: The base directory (project root)
        relative: The relative path to resolve

    Returns:
        Resolved path if safe, None if path traversal attempt
    """
    try:
        resolved = (base / relative).resolve()
        if not resolved.is_relative_to(base):
            return None
        return resolved
    except (ValueError, RuntimeError):
        return None


def tool_read_file(path: str) -> str:
    """
    Read contents of a file from the project.

    Args:
        path: Relative path from project root

    Returns:
        File contents or error message
    """
    # Security check: ensure path stays within project root
    resolved = safe_path(PROJECT_ROOT, path)
    if resolved is None:
        return "Error: Access denied - path traversal not allowed"

    if not resolved.exists():
        return f"Error: File not found: {path}"

    if not resolved.is_file():
        return f"Error: Not a file: {path}"

    try:
        return resolved.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def tool_list_files(path: str) -> str:
    """
    List files and directories in a directory.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing or error message
    """
    # Security check: ensure path stays within project root
    resolved = safe_path(PROJECT_ROOT, path)
    if resolved is None:
        return "Error: Access denied - path traversal not allowed"

    if not resolved.exists():
        return f"Error: Directory not found: {path}"

    if not resolved.is_dir():
        return f"Error: Not a directory: {path}"

    try:
        entries = sorted(resolved.iterdir())
        lines = [e.name for e in entries]
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing directory: {e}"


# Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file from the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": tool_read_file,
    "list_files": tool_list_files,
}


def execute_tool(tool_name: str, args: dict) -> str:
    """
    Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments

    Returns:
        Tool result as string
    """
    if tool_name not in TOOL_FUNCTIONS:
        return f"Error: Unknown tool: {tool_name}"

    func = TOOL_FUNCTIONS[tool_name]
    try:
        return func(**args)
    except Exception as e:
        return f"Error executing {tool_name}: {e}"


def call_llm(messages: list[dict], config: dict) -> dict:
    """
    Call the LLM API and return the response.

    Args:
        messages: List of message dicts for the conversation
        config: LLM configuration

    Returns:
        Parsed LLM response
    """
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.7,
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            return data["choices"][0]["message"]

    except httpx.TimeoutException:
        print("Error: LLM request timed out", file=sys.stderr)
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"Error: HTTP error {e.response.status_code}", file=sys.stderr)
        print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def extract_source_from_messages(messages: list[dict]) -> str:
    """
    Extract source reference from the conversation.

    Looks for file paths mentioned in tool calls or content.

    Args:
        messages: List of message dicts

    Returns:
        Source reference string (e.g., "wiki/file.md#section")
    """
    # Look for read_file tool calls to find which files were read
    for msg in messages:
        if msg.get("role") == "assistant":
            tool_calls = msg.get("tool_calls", [])
            for tc in tool_calls:
                if tc.get("function", {}).get("name") == "read_file":
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        path = args.get("path", "")
                        if path:
                            # Try to extract section from content if possible
                            return f"{path}"
                    except (json.JSONDecodeError, KeyError):
                        pass

    return "wiki"  # Default source


def run_agentic_loop(question: str, config: dict) -> dict:
    """
    Run the agentic loop to answer a question.

    Args:
        question: User's question
        config: LLM configuration

    Returns:
        Result dict with answer, source, and tool_calls
    """
    # System prompt instructs the LLM to use tools and cite sources
    system_prompt = """You are a helpful documentation assistant. You have access to tools that can read files and list directories in a project wiki.

When answering questions:
1. Use list_files to discover what files are available
2. Use read_file to read relevant wiki content
3. Base your answer on the wiki content you read
4. Always include a source reference in the format: wiki/filename.md#section-anchor
5. Stop calling tools once you have enough information to answer

Be concise and accurate. Always cite your sources."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    tool_calls_log = []
    call_count = 0

    while call_count < MAX_TOOL_CALLS:
        call_count += 1
        print(f"\n--- Iteration {call_count} ---", file=sys.stderr)

        # Call LLM
        response = call_llm(messages, config)
        print(f"LLM response type: {response.get('role')}", file=sys.stderr)

        # Check for tool calls
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - LLM provided final answer
            print("LLM provided final answer", file=sys.stderr)
            answer = response.get("content", "")

            # Extract source from the conversation
            source = extract_source_from_messages(messages)

            return {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_log,
            }

        # Add assistant's tool call to messages FIRST
        messages.append(response)

        # Execute tool calls and add results
        for tc in tool_calls:
            function = tc.get("function", {})
            tool_name = function.get("name", "unknown")
            try:
                args = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}

            print(f"Executing tool: {tool_name} with args: {args}", file=sys.stderr)

            # Execute the tool
            result = execute_tool(tool_name, args)

            # Log the tool call
            tool_calls_log.append({
                "tool": tool_name,
                "args": args,
                "result": result,
            })

            # Add tool result to messages (after the assistant message)
            tool_call_id = tc.get("id", f"call_{len(tool_calls_log)}")
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": result,
            })

    # Max iterations reached
    print("Max tool calls reached", file=sys.stderr)
    return {
        "answer": "I reached the maximum number of tool calls (10). Here's what I found:",
        "source": extract_source_from_messages(messages),
        "tool_calls": tool_calls_log,
    }


def main() -> None:
    """Main entry point."""
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    load_env()
    config = get_llm_config()

    # Run agentic loop
    result = run_agentic_loop(question, config)

    # Output JSON result
    print(json.dumps(result))


if __name__ == "__main__":
    main()
