import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from flutter_stripe_mcp.diagnostics import (
    check_android_themes,
    check_gradle_wrapper_version,
    check_ios_camera_permission,
    check_ios_deployment_target,
    check_kotlin_version,
    check_main_activity,
    check_proguard_rules,
)

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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
