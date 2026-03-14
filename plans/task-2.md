# Task 2: The Documentation Agent

## Overview

Build an agentic loop that allows the LLM to use tools (`read_file`, `list_files`) to navigate the project wiki and answer questions with proper source references.

## LLM Provider and Model

- **Provider:** Qwen Code API (self-hosted via qwen-code-oai-proxy on VM)
- **Model:** `qwen3-coder-plus`
- **API Format:** OpenAI-compatible `/v1/chat/completions` endpoint with function calling

## Tool Definitions

### read_file

Read a file from the project repository.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read contents of a file from the project",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root"
      }
    },
    "required": ["path"]
  }
}
```

**Security:**
- Resolve path and ensure it stays within project directory
- Reject paths with `../` traversal attempts
- Return error message if file doesn't exist

### list_files

List files and directories at a given path.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories in a directory",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root"
      }
    },
    "required": ["path"]
  }
}
```

**Security:**
- Resolve path and ensure it stays within project directory
- Reject paths that escape project root
- Return error message if directory doesn't exist

## Agentic Loop

```
1. Send user question + tool definitions to LLM
2. Parse LLM response:
   - If tool_calls present:
     a. Execute each tool call
     b. Append tool results as "tool" role messages
     c. Go to step 1 (max 10 iterations)
   - If text response (no tool calls):
     a. Extract answer and source
     b. Output JSON and exit
```

**Message Flow:**
```
User question → LLM → tool_call → Execute tool → Tool result → LLM → ... → Final answer
```

## System Prompt Strategy

The system prompt will instruct the LLM to:
1. Use `list_files` to discover wiki files when needed
2. Use `read_file` to read relevant wiki content
3. Always include a source reference (file path + section anchor) in the answer
4. Stop calling tools when enough information is gathered

## Path Security

```python
def safe_path(base: Path, relative: str) -> Path | None:
    """Resolve path and ensure it stays within base directory."""
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base):
        return None  # Path traversal attempt
    return resolved
```

## Output Format

```json
{
  "answer": "The answer text",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "file contents..."
    }
  ]
}
```

## Error Handling

- Tool execution errors → return error message as tool result
- Path traversal attempts → return security error
- LLM API errors → exit with error to stderr
- Max 10 tool calls → stop and return best available answer

## Testing Strategy

Two regression tests:

1. **"How do you resolve a merge conflict?"**
   - Expects: `read_file` in tool_calls
   - Expects: `wiki/git-workflow.md` in source

2. **"What files are in the wiki?"**
   - Expects: `list_files` in tool_calls
   - Expects: tool_calls to contain directory listing

## Files to Modify/Create

- `agent.py` - Add tools and agentic loop
- `plans/task-2.md` - This plan
- `AGENT.md` - Update with tool documentation
- `tests/test_agent.py` - Add 2 new tests
