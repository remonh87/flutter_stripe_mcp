# flutter-stripe-mcp

An MCP server that diagnoses Flutter + Stripe Android integration issues — so Claude can check your project setup automatically.

## What it does

| Tool | What it checks |
|------|----------------|
| `diagnose_setup` | Reads your `android/build.gradle` and validates the Kotlin version against flutter_stripe's requirements (min `1.9.0`, latest `2.1.21`) |

## Install

```bash
pip install flutter-stripe-mcp
```

Or with `uv`:

```bash
uv tool install flutter-stripe-mcp
```

## Add to Claude Desktop

Open `~/Library/Application Support/Claude/claude_desktop_config.json` and add:

```json
{
  "mcpServers": {
    "flutter-stripe-mcp": {
      "command": "flutter-stripe-mcp"
    }
  }
}
```

Restart Claude Desktop. Claude will now have access to the diagnostic tools.

## Add to Claude Code

```bash
claude mcp add flutter-stripe-mcp -- flutter-stripe-mcp
```

## Usage

Ask Claude:

> "Check if my Flutter project's Kotlin version is compatible with flutter_stripe. The gradle file is at `/path/to/android/build.gradle`."

Claude will call `diagnose_setup` and tell you exactly what to fix.
