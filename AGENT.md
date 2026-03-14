# Agent Architecture

## Overview

This is an LLM-powered documentation agent that uses tools to navigate the project wiki, read source code, and query the backend API to answer questions. The agent implements an **agentic loop** - it can call tools, observe results, and decide what to do next.

**Task 3 Update:** Added `query_api` tool for querying the backend API with authentication support.

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

### query_api (Task 3)

Query the backend API with optional authentication.

| Parameter | Type | Description |
|-----------|------|-------------|
| `method` | string | HTTP method (GET, POST, PUT, DELETE) |
| `path` | string | API path (e.g., `/items/`, `/analytics/completion-rate`) |
| `body` | string (optional) | JSON request body for POST/PUT requests |
| `include_auth` | boolean (default: true) | Whether to include LMS_API_KEY in Authorization header |

**Returns:** JSON string with `status_code` and `body`, or error message

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` when `include_auth=true`

**Use cases:**

- Data-dependent questions (item counts, scores, analytics)
- Testing API behavior (status codes, error responses)
- Debugging endpoint issues

**Example:** To test authentication error, use `include_auth=false`:

```json
{"tool": "query_api", "args": {"method": "GET", "path": "/items/", "include_auth": false}}
```

## Configuration

The agent reads all configuration from environment variables:

### LLM Configuration (`.env.agent.secret`)

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_KEY` | LLM provider API key | `sk-...` |
| `LLM_API_BASE` | Base URL of the LLM API | `http://10.93.24.145:42005/v1` |
| `LLM_MODEL` | Model name to use | `qwen3-coder-plus` |

### Backend API Configuration (`.env.docker.secret`)

| Variable | Description | Example |
|----------|-------------|---------|
| `LMS_API_KEY` | Backend API key for `query_api` authentication | `my-secret-api-key` |
| `AGENT_API_BASE_URL` | Base URL for backend API (optional) | `http://localhost:42002` |

**Note:** The autochecker injects its own credentials at runtime. Never hardcode values.

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

The system prompt guides the LLM to:

1. Use `list_files` and `read_file` for wiki/documentation questions
2. Use `read_file` for source code questions
3. Use `query_api` for data-dependent questions (counts, scores, analytics)
4. Use `query_api` with `include_auth=false` for authentication error testing
5. Include source references when reading files
6. Provide complete answers immediately (not "let me continue")
7. Stop making tool calls once enough information is gathered

**Tool selection logic:**

- Wiki questions → `list_files`, `read_file`
- Source code questions → `read_file`
- API data questions → `query_api`
- Auth testing → `query_api` with `include_auth=false`

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

## Benchmark Results (Task 3)

**Best score: 8/10 passed**

### Passed Questions

1. ✓ Wiki: Branch protection steps
2. ✓ Wiki: SSH connection guide
3. ✓ Framework detection (FastAPI)
4. ✓ Router modules listing (unstable, ~50%)
5. ✓ Item count from database
6. ✓ Auth error status code (401)
7. ✓ Analytics completion-rate error
8. ✓ Top-learners bug diagnosis

### Challenges

- **Question 9** (request lifecycle): LLM sometimes doesn't complete the answer
- **Question 10** (ETL idempotency): Not reached due to Q9 failure
- **Question 4 instability**: LLM non-determinism causes ~50% pass rate

## Lessons Learned

1. **Tool descriptions matter**: Adding examples like `"backend/app/routers"` in tool descriptions helps the LLM use correct paths from the first attempt.

2. **Explicit instructions improve completion**: Telling the LLM "do not say 'let me continue'" reduces incomplete answers, but doesn't eliminate them entirely.

3. **Flexible authentication**: The `include_auth=false` parameter enables testing authentication errors (401/403 responses) without modifying the tool implementation.

4. **LLM variability**: The same prompt produces different results across runs. Stability requires careful prompt engineering and possibly multiple retry strategies.

5. **Iteration limits**: Increased `MAX_TOOL_CALLS` from 10 to 15 to accommodate complex multi-step queries that require reading multiple files.

6. **Source extraction**: Updated `extract_source_from_messages()` to handle both file paths (`read_file`) and API endpoints (`query_api`).

7. **Environment variable separation**: Keeping `LLM_API_KEY` (for LLM provider) separate from `LMS_API_KEY` (for backend API) prevents confusion and security issues.

## Files (Updated)

| File | Description |
|------|-------------|
| `agent.py` | Main CLI script with agentic loop and `query_api` tool |
| `.env.agent.secret` | LLM configuration (gitignored) |
| `.env.docker.secret` | Backend API credentials (gitignored) |
| `plans/task-3.md` | Implementation plan and benchmark diagnosis |
| `AGENT.md` | This documentation |
| `tests/test_agent.py` | Regression tests |
