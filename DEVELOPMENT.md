# Development

## Setup

```bash
uv sync
```

## Tests

```bash
uv run pytest
```

## Running with MCP Inspector

[MCP Inspector](https://modelcontextprotocol.io/docs/tools/inspector) lets you call the server's tools directly from a browser UI, without wiring it into Claude Desktop or Claude Code.

From the repo root:

```bash
npx @modelcontextprotocol/inspector uv run flutter-stripe-mcp
```

This starts the inspector and launches `flutter-stripe-mcp` (the `stdio` entry point defined in `pyproject.toml`) as its child process. Open the URL printed in the terminal, then:

1. Click **Connect** (transport is already set to `stdio`, command `uv run flutter-stripe-mcp`).
2. Go to the **Tools** tab and click **List Tools** to see `diagnose_setup`, `search_flutter_stripe_issues`, and `get_flutter_stripe_issue`.
3. Select a tool, fill in its arguments, and click **Run** to see the raw JSON result.

Useful sample inputs:

| Tool | Example arguments |
|------|--------------------|
| `diagnose_setup` | `project_path`: absolute path to a fixture in `testfiles/`, e.g. `.../flutter_stripe_mcp/testfiles/project_with_issues` |
| `search_flutter_stripe_issues` | `query`: `PaymentSheet crash` |
| `get_flutter_stripe_issue` | `issue_number`: a number returned by a search above |

If you change code in `flutter_stripe_mcp/`, stop the inspector (Ctrl+C) and re-run the command — it re-launches the server with your latest changes; there's no hot reload.

## Project structure

- `flutter_stripe_mcp/server.py` — MCP tool registration (`FastMCP`).
- `flutter_stripe_mcp/diagnostics.py` — local file checks used by `diagnose_setup`.
- `flutter_stripe_mcp/github_issues.py` — GitHub API calls used by the issue-search tools.
- `tests/` — pytest suite; `testfiles/` holds fixture Flutter project trees used by `diagnose_setup` tests.
