from typing import Any

from mcp.server.fastmcp import FastMCP

from diagnostics import check_kotlin_version

mcp = FastMCP("flutter-stripe-mcp")


@mcp.tool()
def diagnose_setup(build_gradle_path: str) -> dict[str, Any]:
    """
    Diagnose the Flutter + Stripe Android setup from a project-level Gradle file.

    Reads the build.gradle or build.gradle.kts file at the given path, detects
    the Kotlin version (supporting Groovy DSL, Kotlin DSL, and ext block forms),
    and checks it against flutter_stripe's minimum requirement (1.9.0) and the
    latest recommended stable Kotlin version (2.1.21 as of mid-2025).

    Args:
        build_gradle_path: Absolute path to the project-level build.gradle or
                           build.gradle.kts file (e.g. /path/to/android/build.gradle).

    Returns:
        A dict with keys:
          - kotlin_version_found (bool)
          - detected_version (str | None)
          - meets_minimum_requirement (bool | None): None on I/O error
          - minimum_required (str): "1.9.0"
          - is_up_to_date (bool | None): None on I/O error
          - latest_recommended (str): "2.1.21"
          - status (str): "ok", "outdated", "missing", or "error"
          - suggestion (str | None): fix instructions, or None when status is "ok"
    """
    return check_kotlin_version(build_gradle_path)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
