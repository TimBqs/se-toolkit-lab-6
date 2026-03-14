# Agent Architecture

## Overview

This is a simple LLM-powered CLI agent that answers questions by calling an LLM API. This is Task 1 of the lab - the foundation for future tasks where tools and agentic behavior will be added.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted via qwen-code-oai-proxy on VM)
- **Model:** `qwen3-coder-plus`
- **API Format:** OpenAI-compatible `/v1/chat/completions` endpoint

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Command    │────▶│   agent.py  │────▶│  LLM API    │────▶│   JSON      │
│  Line Arg   │     │  (CLI)      │     │  (Qwen)     │     │   Output    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## Data Flow

1. **Input:** User provides a question as a command-line argument
2. **Environment Loading:** `agent.py` loads `.env.agent.secret` for API credentials
3. **API Call:** HTTP POST to the LLM's `/chat/completions` endpoint
4. **Response Parsing:** Extract answer from `choices[0].message.content`
5. **Output:** Print JSON with `answer` and `tool_calls` fields

## Configuration

The agent reads configuration from `.env.agent.secret` in the project root:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | API key for authentication | `sk-...` |
| `LLM_API_BASE` | Base URL of the LLM API | `http://192.168.1.100:42005/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

## Usage

```bash
# Run with a question
uv run agent.py "What does REST stand for?"

# Example output
{"answer": "Representational State Transfer.", "tool_calls": []}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "<the LLM's response>",
  "tool_calls": []
}
```

- `answer` (string): The LLM's answer to the question
- `tool_calls` (array): Empty for Task 1 (will be populated in Task 2)

## Error Handling

- All error messages are printed to **stderr**
- Only valid JSON is printed to **stdout**
- Exit code 0 on success, 1 on error

Possible errors:
- Missing command-line argument
- Missing environment variables
- API timeout (60 second limit)
- HTTP errors from the LLM API

## Dependencies

- `httpx` - HTTP client for API calls
- `python-dotenv` - Environment variable loading
- Standard library: `json`, `os`, `sys`, `pathlib`

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script |
| `.env.agent.secret` | LLM configuration (gitignored) |
| `plans/task-1.md` | Implementation plan |
| `AGENT.md` | This documentation |

## Testing

Run the regression test:

```bash
pytest tests/test_agent.py
```

The test verifies:
- `agent.py` runs successfully with a question
- Output is valid JSON
- `answer` field exists and is non-empty
- `tool_calls` field exists and is an empty list
