import re
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("flutter-stripe-mcp")

KOTLIN_MIN_VERSION = "1.9.0"
KOTLIN_LATEST_VERSION = "2.1.21"

# Patterns tried in order; first match wins.
_KOTLIN_VERSION_PATTERNS: list[re.Pattern[str]] = [
    # ext.kotlin_version = "1.9.0"  /  kotlin_version = '1.9.0' inside ext {}
    re.compile(r'(?:ext\.)?kotlin_version\s*=\s*["\'](\d+\.\d+\.\d+)["\']'),
    # id("org.jetbrains.kotlin.android") version "1.9.0"  (Kotlin DSL)
    re.compile(r'id\s*\(\s*["\']org\.jetbrains\.kotlin\.[^"\']+["\']\s*\)\s+version\s+["\'](\d+\.\d+\.\d+)["\']'),
    # id 'org.jetbrains.kotlin.android' version '1.9.0'  (Groovy DSL)
    re.compile(r"""id\s+["']org\.jetbrains\.kotlin\.[^"']+["']\s+version\s+["'](\d+\.\d+\.\d+)["']"""),
]


def _parse_version(version_str: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version_str.split("."))


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
    try:
        with open(build_gradle_path, encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        return {
            "kotlin_version_found": False,
            "detected_version": None,
            "meets_minimum_requirement": None,
            "minimum_required": KOTLIN_MIN_VERSION,
            "is_up_to_date": None,
            "latest_recommended": KOTLIN_LATEST_VERSION,
            "status": "error",
            "suggestion": f"File not found: {build_gradle_path}",
        }
    except OSError as exc:
        return {
            "kotlin_version_found": False,
            "detected_version": None,
            "meets_minimum_requirement": None,
            "minimum_required": KOTLIN_MIN_VERSION,
            "is_up_to_date": None,
            "latest_recommended": KOTLIN_LATEST_VERSION,
            "status": "error",
            "suggestion": f"Could not read file: {exc}",
        }

    detected_version: str | None = None
    for pattern in _KOTLIN_VERSION_PATTERNS:
        match = pattern.search(content)
        if match:
            detected_version = match.group(1)
            break

    if detected_version is None:
        return {
            "kotlin_version_found": False,
            "detected_version": None,
            "meets_minimum_requirement": False,
            "minimum_required": KOTLIN_MIN_VERSION,
            "is_up_to_date": False,
            "latest_recommended": KOTLIN_LATEST_VERSION,
            "status": "missing",
            "suggestion": (
                f"No Kotlin version detected in {build_gradle_path}. Add one of:\n"
                f'  Kotlin DSL:  id("org.jetbrains.kotlin.android") version "{KOTLIN_LATEST_VERSION}"\n'
                f"  Groovy DSL:  ext.kotlin_version = '{KOTLIN_LATEST_VERSION}'"
            ),
        }

    detected_t = _parse_version(detected_version)
    min_t = _parse_version(KOTLIN_MIN_VERSION)
    latest_t = _parse_version(KOTLIN_LATEST_VERSION)

    meets_minimum = detected_t >= min_t
    is_up_to_date = detected_t >= latest_t

    if not meets_minimum:
        status = "outdated"
        suggestion = (
            f"Kotlin {detected_version} is below the minimum {KOTLIN_MIN_VERSION} "
            f"required by flutter_stripe. Update to {KOTLIN_LATEST_VERSION}."
        )
    elif not is_up_to_date:
        status = "outdated"
        suggestion = (
            f"Kotlin {detected_version} meets the minimum requirement but is not "
            f"the latest recommended version ({KOTLIN_LATEST_VERSION}). Consider upgrading."
        )
    else:
        status = "ok"
        suggestion = None

    return {
        "kotlin_version_found": True,
        "detected_version": detected_version,
        "meets_minimum_requirement": meets_minimum,
        "minimum_required": KOTLIN_MIN_VERSION,
        "is_up_to_date": is_up_to_date,
        "latest_recommended": KOTLIN_LATEST_VERSION,
        "status": status,
        "suggestion": suggestion,
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
