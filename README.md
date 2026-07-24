# flutter-stripe-mcp

An MCP server that diagnoses Flutter + Stripe ([flutter_stripe](https://pub.dev/packages/flutter_stripe)) setup issues — so Claude can check your project automatically.

## What it does

Three tools: one diagnoses your local project setup, and two search GitHub for known issues and their fixes.

`diagnose_setup` takes the path to your Flutter project root and runs every check:

| Check | Requirement |
|-------|-------------|
| `kotlin` | Kotlin version >= 1.9.0 (read from `android/settings.gradle` or legacy `android/build.gradle`) |
| `gradle_wrapper` | Gradle wrapper >= 8.0 |
| `android_themes` | Theme styles derive from `Theme.AppCompat.*`, `Theme.MaterialComponents.*`, or `Theme.Material3.*` |
| `main_activity` | `MainActivity` extends `FlutterFragmentActivity` (not `FlutterActivity`) |
| `proguard_rules` | `proguard-rules.pro` contains all required Stripe rules |
| `ios_deployment_target` | iOS deployment target >= 13.0 (from `Podfile` or `project.pbxproj`) |
| `ios_camera_permission` | `NSCameraUsageDescription` set in `Info.plist` (suggestion — needed for card scanning) |

The result lists passing checks by name and returns a `fix` instruction for each problem found. Platforms without an `android/` or `ios/` directory are skipped.

### Checking for known issues

Two more tools let Claude check whether a problem is already a documented issue in the [flutter_stripe GitHub repo](https://github.com/flutter-stripe/flutter_stripe), and read the fix straight from the discussion:

| Tool | Purpose |
|------|---------|
| `search_flutter_stripe_issues(query, state="all", limit=10)` | Search issues by keywords (e.g. an error message); returns titles, state, and short excerpts. |
| `get_flutter_stripe_issue(issue_number)` | Fetch one issue's full body and all comments, to find the actual fix. |

These use GitHub's public search API, which is limited to 60 requests/hour unauthenticated. If you hit the rate limit, the tool returns a clear error instead of failing silently. Optionally, set a `GITHUB_TOKEN` (or `GH_TOKEN`) environment variable to raise this to 5,000 requests/hour — no other configuration needed.

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

Restart Claude Desktop. Claude will now have access to the diagnostic tool.

## Add to Claude Code

```bash
claude mcp add flutter-stripe-mcp -- flutter-stripe-mcp
```

## Usage

Ask Claude:

> "Check if my Flutter project at `/path/to/myapp` is set up correctly for flutter_stripe."

Claude calls `diagnose_setup` with the project root and tells you exactly what to fix.

## Development

```bash
uv sync
uv run pytest
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for running the server locally with MCP Inspector.
