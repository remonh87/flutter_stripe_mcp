import re
from typing import Any

KOTLIN_MIN_VERSION = "1.9.0"
KOTLIN_LATEST_VERSION = "2.1.21"

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


def check_kotlin_version(build_gradle_path: str) -> dict[str, Any]:
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
