import os
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from flutter_stripe_mcp.diagnostics import (
    check_android_themes,
    check_gradle_wrapper_version,
    check_ios_camera_permission,
    check_ios_deployment_target,
    check_kotlin_version,
    check_main_activity,
    check_proguard_rules,
)
from flutter_stripe_mcp.github_issues import get_issue, search_issues

mcp = FastMCP("flutter-stripe-mcp")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, idempotentHint=True, openWorldHint=False
    )
)
def diagnose_setup(project_path: str) -> dict[str, Any]:
    """Diagnose a Flutter + Stripe (flutter_stripe) project setup.

    Android checks: Kotlin version, Gradle wrapper version, theme parents,
    MainActivity base class, ProGuard rules. iOS checks: minimum deployment
    target, camera usage permission.

    Args:
        project_path: Absolute path to the Flutter project root (the directory
            containing android/ and ios/).

    Returns:
        {"ok": [names of passed checks],
         "issues": [{"check", "status", "fix", ...} for each problem found]}
    """
    if not os.path.isdir(project_path):
        return {"error": f"Project path not found or not a directory: {project_path}"}

    android_path = os.path.join(project_path, "android")
    ios_path = os.path.join(project_path, "ios")

    results: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []

    if os.path.isdir(android_path):
        src_path = os.path.join(android_path, "app", "src")
        results["kotlin"] = check_kotlin_version(android_path)
        results["gradle_wrapper"] = check_gradle_wrapper_version(
            os.path.join(android_path, "gradle", "wrapper", "gradle-wrapper.properties")
        )
        results["android_themes"] = check_android_themes(src_path)
        results["main_activity"] = check_main_activity(src_path)
        results["proguard_rules"] = check_proguard_rules(
            os.path.join(android_path, "app")
        )
    else:
        skipped.append("android (no android/ directory)")

    if os.path.isdir(ios_path):
        results["ios_deployment_target"] = check_ios_deployment_target(ios_path)
        results["ios_camera_permission"] = check_ios_camera_permission(ios_path)
    else:
        skipped.append("ios (no ios/ directory)")

    report: dict[str, Any] = {
        "ok": [name for name, r in results.items() if r["status"] == "ok"],
        "issues": [
            {"check": name, **r} for name, r in results.items() if r["status"] != "ok"
        ],
    }
    if skipped:
        report["skipped"] = skipped
    return report


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, idempotentHint=True, openWorldHint=True
    )
)
def search_flutter_stripe_issues(
    query: str,
    state: Literal["all", "open", "closed"] = "all",
    limit: Annotated[int, Field(ge=1, le=30)] = 10,
) -> dict[str, Any]:
    """Search GitHub issues in the flutter_stripe repository (flutter-stripe/flutter_stripe).

    Use this to check whether a problem you're debugging (an error message,
    a crash, an unexpected behavior) is already a known, reported issue —
    before assuming it's novel or trying to work around it from scratch.
    Returns short excerpts so you can judge relevance; call
    get_flutter_stripe_issue with a specific issue number to read the full
    discussion and find the documented fix or workaround.

    If an exact-match search (all words present) finds nothing, this
    automatically retries with a broader "any of these words" search and
    marks the result with "broadened_search": true — treat those results
    as lower-confidence and check relevance via the excerpt before
    following up with get_flutter_stripe_issue.

    Args:
        query: Free-text search terms (e.g. an error message or symptom).
        state: "all" (default), "open", or "closed".
        limit: Max number of results to return (1-30).

    Returns:
        {"total_count": int, "results": [{"number", "title", "state", "url", "excerpt"}]}
        (plus "broadened_search"/"note" if a broader fallback search was used),
        or {"error": "...", "kind": "..."} on failure (e.g. rate-limited).
    """
    return search_issues(query, state=state, limit=limit)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True, idempotentHint=True, openWorldHint=True
    )
)
def get_flutter_stripe_issue(issue_number: int) -> dict[str, Any]:
    """Fetch the full body and comments of one flutter_stripe GitHub issue.

    Use this after search_flutter_stripe_issues has identified a candidate
    issue number, to read the complete discussion — maintainer replies and
    community comments often contain the actual fix, workaround, or root
    cause that a title/excerpt alone won't reveal.

    Args:
        issue_number: The GitHub issue number (e.g. 1234), not a URL.

    Returns:
        {"number", "title", "state", "url", "body", "comments": [{"author", "body"}]}
        (plus "note" if the comment thread was too long to fetch in full),
        or {"error": "...", "kind": "..."} on failure (e.g. not found).
    """
    return get_issue(issue_number)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
