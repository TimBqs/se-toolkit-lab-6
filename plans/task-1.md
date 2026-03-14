# Task 1: Call an LLM from Code

## LLM Provider and Model

- **Provider:** Qwen Code API (self-hosted on VM via qwen-code-oai-proxy)
- **Model:** `qwen3-coder-plus`
- **API Format:** OpenAI-compatible `/v1/chat/completions` endpoint

## Architecture

### Input/Output

- **Input:** Command-line argument (question string)
- **Output:** Single JSON line to stdout with `answer` and `tool_calls` fields

### Data Flow

```
Command line → agent.py → Load .env.agent.secret → HTTP POST to LLM API → Parse response → JSON output
```

### Components

1. **Argument parsing** - Read question from `sys.argv[1]`
2. **Environment loading** - Use `python-dotenv` to load `.env.agent.secret`
3. **HTTP client** - Use `httpx` (already in dependencies) to call LLM API
4. **Response parsing** - Extract `choices[0].message.content` from API response
5. **JSON formatting** - Output `{"answer": "...", "tool_calls": []}`

### Error Handling

- Missing argument → print error to stderr, exit code 1
- Missing env vars → print error to stderr, exit code 1
- API error/timeout → print error to stderr, exit code 1
- All errors logged to stderr, only valid JSON to stdout

### Dependencies

- `httpx` - HTTP client (already in pyproject.toml)
- `python-dotenv` - Environment variable loading (need to add)
- `json` - Standard library
- `sys` - Standard library

## Testing Strategy

One regression test that:
1. Runs `agent.py "test question"` as subprocess
2. Parses stdout as JSON
3. Verifies `answer` field exists and is non-empty string
4. Verifies `tool_calls` field exists and is empty list

## Files to Create

- `plans/task-1.md` - This plan
- `agent.py` - Main CLI script
- `AGENT.md` - Documentation
- `tests/test_agent.py` - Regression test
