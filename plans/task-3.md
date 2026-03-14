# Task 3: The System Agent — Implementation Plan

## Overview

This task extends the Task 2 documentation agent with a new `query_api` tool that allows the agent to query the deployed backend API. The agent will answer two new kinds of questions:

1. **Static system facts** — framework, ports, status codes (from source code)
2. **Data-dependent queries** — item count, scores, analytics (from live API)

## Tool Design: `query_api`

### Function Schema

```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Send an HTTP request to the backend API. Use for data-dependent questions like item counts, analytics, or testing endpoint behavior.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {
          "type": "string",
          "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
        },
        "path": {
          "type": "string",
          "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
        },
        "body": {
          "type": "string",
          "description": "Optional JSON request body for POST/PUT requests"
        }
      },
      "required": ["method", "path"]
    }
  }
}
```

### Implementation

```python
def tool_query_api(method: str, path: str, body: str | None = None) -> str:
    """
    Query the backend API with authentication.
    
    Returns JSON string with status_code and body.
    Uses LMS_API_KEY from .env.docker.secret for authentication.
    """
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY")
    
    url = f"{base_url}{path}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Send request with httpx
    # Return: json.dumps({"status_code": ..., "body": ...})
```

## Environment Variables

The agent must read all configuration from environment variables:

| Variable | Purpose | Source | Default |
|----------|---------|--------|---------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` | — |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` | — |
| `LLM_MODEL` | Model name | `.env.agent.secret` | — |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` | — |
| `AGENT_API_BASE_URL` | Base URL for `query_api` | `.env.docker.secret` or env | `http://localhost:42002` |

**Important:** The autochecker runs with different credentials. Never hardcode values.

## System Prompt Update

Update the system prompt to guide the LLM on tool selection:

```
You are a helpful documentation assistant. You have access to tools that can:
1. Read files and list directories in the project wiki and source code
2. Query the backend API for live data

When answering questions:
- For wiki/documentation questions: use list_files and read_file
- For source code questions: use read_file to examine code
- For data-dependent questions (counts, scores, analytics): use query_api
- For API behavior questions (status codes, errors): use query_api
- Always cite sources when reading files
- Stop calling tools once you have enough information
```

## Implementation Steps

1. **Add `LMS_API_KEY` loading** — Update `get_llm_config()` or create `get_api_config()` to read backend credentials
2. **Implement `tool_query_api()`** — HTTP client with authentication
3. **Add tool schema to `TOOLS`** — Register with LLM for function calling
4. **Update `TOOL_FUNCTIONS`** — Map `query_api` to implementation
5. **Update system prompt** — Guide tool selection
6. **Update `extract_source_from_messages()`** — Handle cases where source is optional (system questions)

## Testing Strategy

### Unit Tests (2 new tests in `tests/test_agent.py`)

1. **Test system fact question** — "What framework does the backend use?" → expects `read_file`
2. **Test data query question** — "How many items are in the database?" → expects `query_api`

### Benchmark Testing

Run `uv run run_eval.py` and iterate:

| Question | Expected Tool | Notes |
|----------|---------------|-------|
| 0. Wiki: protect branch | `read_file` | Wiki lookup |
| 1. Wiki: SSH connection | `read_file` | Wiki lookup |
| 2. Framework from source | `read_file` | Read backend code |
| 3. API router modules | `list_files` | List backend routers |
| 4. Item count | `query_api` | GET /items/ |
| 5. Status code without auth | `query_api` | GET /items/ without header |
| 6. Analytics error | `query_api` + `read_file` | Multi-step |
| 7. Top-learners bug | `query_api` + `read_file` | Multi-step |
| 8. Request lifecycle | `read_file` | LLM judge |
| 9. ETL idempotency | `read_file` | LLM judge |

## Initial Benchmark Score

**Best run: 8/10 passed**

- ✓ Questions 1-8: Passed (wiki lookups, framework detection, router listing, item count, auth error, analytics bugs)
- ✗ Question 9: Request lifecycle — LLM doesn't complete answer (says "let me continue")
- ✗ Question 10: ETL idempotency — Not reached

**Note:** Question 4 (router modules) is unstable — passes ~50% of runs due to LLM non-determinism. The LLM sometimes completes the answer immediately, sometimes continues iterating.

## Known Challenges

1. **LLM non-determinism** — The same prompt produces different behavior across runs. Question 4 passes ~50% of the time.
2. **Incomplete answers** — LLM sometimes says "let me continue" instead of providing the final answer.
3. **Multi-step reasoning** — Questions 6-7 require chaining `query_api` then `read_file` to diagnose bugs.
4. **LLM judge questions** — Questions 8-9 use rubric-based judging on the bot side for open-ended answers.
5. **Tool selection** — LLM must distinguish between wiki, source code, and API questions.

## Iteration Strategy

1. ✓ Run `run_eval.py` to see first failure
2. ✓ Check which tool was called (or not called)
3. ✓ Adjust tool descriptions and system prompt
4. ✓ Added `include_auth` parameter for authentication testing
5. ✓ Updated prompt to discourage "let me continue" phrasing
6. Continue iterating on prompt engineering for stability

## Lessons Learned

1. **Tool descriptions matter** — Adding examples like `"backend/app/routers"` in the description helps the LLM use correct paths.
2. **Explicit instructions** — Telling the LLM "do not say 'let me continue'" improves completion rates.
3. **Auth flexibility** — The `include_auth=false` parameter enables testing authentication errors.
4. **LLM variability** — The same prompt can produce different results; stability requires careful prompt engineering.
5. **Max iterations** — Increased from 10 to 15 to allow complex multi-step queries.
