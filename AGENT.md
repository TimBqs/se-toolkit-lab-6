# Agent Architecture

## Overview

This is an LLM-powered documentation agent that uses tools to navigate the project wiki and answer questions with proper source references. The agent implements an **agentic loop** - it can call tools, observe results, and decide what to do next.

## LLM Provider

- **Provider:** Qwen Code API (self-hosted via qwen-code-oai-proxy on VM)
- **Model:** `qwen3-coder-plus`
- **API Format:** OpenAI-compatible `/v1/chat/completions` endpoint with function calling

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Command    │────▶│   agent.py  │────▶│  LLM API    │────▶│  Tool Call  │
│  Line Arg   │     │  (CLI)      │     │  (Qwen)     │     │  Decision   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   JSON      │◀────│   Answer    │◀────│  Final      │◀────│  Execute    │
│   Output    │     │  + Source   │     │  Response   │     │  Tool       │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

## Agentic Loop

The agent follows this loop:

1. **Send** user question + tool definitions to LLM
2. **Parse** LLM response:
   - **If tool_calls present:**
     - Execute each tool
     - Append results as "tool" role messages
     - Go to step 1 (max 10 iterations)
   - **If text response (no tool calls):**
     - Extract answer and source
     - Output JSON and exit

### Message Flow

```
User: "How do you resolve a merge conflict?"
  │
  ▼
LLM: [tool_call: list_files(path="wiki")]
  │
  ▼
Agent: [tool_result: "git-workflow.md\n..."]
  │
  ▼
LLM: [tool_call: read_file(path="wiki/git-workflow.md")]
  │
  ▼
Agent: [tool_result: "# Git Workflow\n...resolving merge conflicts..."]
  │
  ▼
LLM: [final_answer: "Edit the conflicting file..." source: "wiki/git-workflow.md"]
  │
  ▼
Output: {"answer": "...", "source": "...", "tool_calls": [...]}
```

## Tools

### read_file

Read contents of a file from the project repository.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative path from project root (e.g., `wiki/git-workflow.md`) |

**Returns:** File contents as string, or error message

**Security:**
- Rejects paths with `../` traversal attempts
- Cannot read files outside project directory

### list_files

List files and directories in a directory.

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | string | Relative directory path from project root (e.g., `wiki`) |

**Returns:** Newline-separated listing, or error message

**Security:**
- Rejects paths that escape project root
- Cannot list directories outside project directory

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
uv run agent.py "How do you resolve a merge conflict?"

# Example output
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "# Git Workflow\n..."
    }
  ]
}
```

## Output Format

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "<the answer text>",
  "source": "<wiki section reference>",
  "tool_calls": [
    {
      "tool": "<tool name>",
      "args": {<arguments>},
      "result": "<tool result>"
    }
  ]
}
```

- `answer` (string): The LLM's answer to the question
- `source` (string): Reference to the wiki section used (e.g., `wiki/git-workflow.md`)
- `tool_calls` (array): All tool calls made during the agentic loop

## System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover available wiki files
2. Use `read_file` to read relevant content
3. Base answers on wiki content read
4. Always include a source reference
5. Stop calling tools when enough information is gathered

## Error Handling

- All error messages are printed to **stderr**
- Only valid JSON is printed to **stdout**
- Exit code 0 on success, 1 on error

Possible errors:
- Missing command-line argument
- Missing environment variables
- API timeout (60 second limit)
- HTTP errors from the LLM API
- Tool execution errors (returned as tool result)
- Path traversal attempts (blocked by security check)

## Path Security

The agent prevents directory traversal attacks:

```python
def safe_path(base: Path, relative: str) -> Path | None:
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base):
        return None  # Path traversal attempt blocked
    return resolved
```

## Dependencies

- `httpx` - HTTP client for API calls
- `python-dotenv` - Environment variable loading
- Standard library: `json`, `os`, `sys`, `pathlib`, `typing`

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script with agentic loop |
| `.env.agent.secret` | LLM configuration (gitignored) |
| `plans/task-2.md` | Implementation plan |
| `AGENT.md` | This documentation |
| `tests/test_agent.py` | Regression tests |

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

Tests verify:
- Agent outputs valid JSON
- `answer`, `source`, and `tool_calls` fields exist
- Correct tools are called for specific questions
- Tool results are properly captured
