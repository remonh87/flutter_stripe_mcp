from typing import Any

from mcp.server.fastmcp import FastMCP

from diagnostics import (
    check_android_themes,
    check_gradle_wrapper_version,
    check_ios_camera_permission,
    check_ios_deployment_target,
    check_kotlin_version,
    check_main_activity,
    check_proguard_rules,
)

mcp = FastMCP("flutter-stripe-mcp")


@mcp.tool()
def diagnose_setup(
    build_gradle_path: str | None = None,
    gradle_wrapper_path: str | None = None,
    android_src_path: str | None = None,
    android_app_path: str | None = None,
    ios_path: str | None = None,
) -> dict[str, Any]:
    """
    Diagnose the Flutter + Stripe Android and iOS setup.

    Always runs the Kotlin version check. Optionally runs additional checks when the
    corresponding paths are supplied.

    Args:
        build_gradle_path: Optional absolute path to the project-level build.gradle or
                           build.gradle.kts file (e.g. /path/to/android/build.gradle).
                           When provided, checks the Kotlin version.
        gradle_wrapper_path: Optional absolute path to gradle-wrapper.properties
                             (e.g. /path/to/android/gradle/wrapper/gradle-wrapper.properties).
                             When provided, checks that the Gradle wrapper version is >= 8.0.
        android_src_path: Optional absolute path to the Android app src directory
                          (e.g. /path/to/android/app/src). When provided:
                          - Scans styles.xml/themes.xml and checks theme parents.
                          - Scans for MainActivity and checks it extends FlutterFragmentActivity.
        android_app_path: Optional absolute path to the Android app directory
                          (e.g. /path/to/android/app). When provided, checks that
                          proguard-rules.pro contains all required Stripe rules (fetched
                          from the canonical online reference when network is available).
        ios_path: Optional absolute path to the iOS directory of the Flutter project
                  (e.g. /path/to/myapp/ios). When provided:
                  - Checks the minimum iOS deployment target is >= 13.0, reading from
                    the Podfile (CocoaPods) or Runner.xcodeproj/project.pbxproj (SPM).
                  - Checks whether NSCameraUsageDescription is present in
                    Runner/Info.plist (suggested for card scanning; reported as a
                    suggestion, not an error).

    Returns:
        A dict with one or more of the following keys (a key is only present when the
        corresponding path argument was supplied):
          - kotlin (dict): result of the Kotlin version check.
          - gradle_wrapper (dict): result of the Gradle wrapper version check.
          - android_themes (dict): result of the Android theme parent check.
          - main_activity (dict): result of the MainActivity base class check.
          - proguard_rules (dict): result of the ProGuard Stripe rules check.
          - ios_deployment_target (dict): result of the iOS minimum deployment target check.
          - ios_camera_permission (dict): result of the NSCameraUsageDescription check.

        Each sub-dict contains a "status" field and a "suggestion" field (str or None).
    """
    result: dict[str, Any] = {}
    if build_gradle_path is not None:
        result["kotlin"] = check_kotlin_version(build_gradle_path)
    if gradle_wrapper_path is not None:
        result["gradle_wrapper"] = check_gradle_wrapper_version(gradle_wrapper_path)
    if android_src_path is not None:
        result["android_themes"] = check_android_themes(android_src_path)
        result["main_activity"] = check_main_activity(android_src_path)
    if android_app_path is not None:
        result["proguard_rules"] = check_proguard_rules(android_app_path)
    if ios_path is not None:
        result["ios_deployment_target"] = check_ios_deployment_target(ios_path)
        result["ios_camera_permission"] = check_ios_camera_permission(ios_path)
    return result


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
