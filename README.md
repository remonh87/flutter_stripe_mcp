# flutter-stripe-mcp

An MCP server that diagnoses Flutter + Stripe ([flutter_stripe](https://pub.dev/packages/flutter_stripe)) setup issues — so Claude can check your project automatically.

## What it does

One tool, `diagnose_setup`, takes the path to your Flutter project root and runs every check:

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
