#!/usr/bin/env python3
"""
LLM Agent CLI - Task 1

A simple CLI that takes a question, sends it to an LLM, and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    {"answer": "...", "tool_calls": []}
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


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


def call_lllm(question: str, config: dict) -> str:
    """
    Call the LLM API and return the answer.

    Args:
        question: The user's question
        config: LLM configuration (api_key, api_base, model)

    Returns:
        The LLM's answer as a string
    """
    url = f"{config['api_base']}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
    }

    print(f"Calling LLM at {url}...", file=sys.stderr)

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            # Extract answer from OpenAI-compatible response
            answer = data["choices"][0]["message"]["content"]
            return answer

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

    # Call LLM and get answer
    answer = call_lllm(question, config)

    # Output JSON result
    result = {
        "answer": answer,
        "tool_calls": [],
    }

    # Only valid JSON to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
