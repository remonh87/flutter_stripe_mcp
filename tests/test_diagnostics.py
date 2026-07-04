import os

from flutter_stripe_mcp.diagnostics import check_kotlin_version
from flutter_stripe_mcp.server import diagnose_setup

TESTFILES = os.path.join(os.path.dirname(__file__), "..", "testfiles")

ALL_CHECKS = {
    "kotlin",
    "gradle_wrapper",
    "android_themes",
    "main_activity",
    "proguard_rules",
    "ios_deployment_target",
    "ios_camera_permission",
}


def _issues_by_check(report):
    return {issue["check"]: issue for issue in report["issues"]}


def test_project_ok_passes_all_checks():
    report = diagnose_setup(os.path.join(TESTFILES, "project_ok"))
    assert report["issues"] == []
    assert set(report["ok"]) == ALL_CHECKS
    assert "skipped" not in report


def test_project_with_issues_flags_every_check():
    report = diagnose_setup(os.path.join(TESTFILES, "project_with_issues"))
    assert report["ok"] == []
    issues = _issues_by_check(report)
    assert set(issues) == ALL_CHECKS

    assert issues["kotlin"]["status"] == "outdated"
    assert issues["kotlin"]["detected"] == "1.3.10"

    assert issues["gradle_wrapper"]["status"] == "outdated"
    assert issues["gradle_wrapper"]["detected"] == "7.6.3"

    assert issues["android_themes"]["status"] == "invalid_theme_parent"
    assert "Theme.Holo.Light.DarkActionBar" in issues["android_themes"]["fix"]
    assert "@android:style/Theme.Light" in issues["android_themes"]["fix"]

    assert issues["main_activity"]["status"] == "wrong_base_class"
    assert "extends FlutterActivity" in issues["main_activity"]["fix"]

    assert issues["proguard_rules"]["status"] == "missing_rules"
    assert "-keep class com.stripe.** { *; }" in issues["proguard_rules"]["fix"]

    # No Podfile in this fixture, so the version comes from project.pbxproj.
    assert issues["ios_deployment_target"]["status"] == "outdated"
    assert issues["ios_deployment_target"]["detected"] == "12.0"

    assert issues["ios_camera_permission"]["status"] == "suggestion"


def test_nonexistent_project_path():
    report = diagnose_setup("/nonexistent/path")
    assert "error" in report


def test_ios_only_project_skips_android(tmp_path):
    (tmp_path / "ios" / "Runner").mkdir(parents=True)
    report = diagnose_setup(str(tmp_path))
    assert report["skipped"] == ["android (no android/ directory)"]
    issues = _issues_by_check(report)
    assert set(issues) == {"ios_deployment_target", "ios_camera_permission"}


def test_kotlin_legacy_ext_version(tmp_path):
    (tmp_path / "build.gradle").write_text(
        "buildscript {\n    ext.kotlin_version = '1.7.10'\n}\n"
    )
    result = check_kotlin_version(str(tmp_path))
    assert result["status"] == "outdated"
    assert result["detected"] == "1.7.10"


def test_kotlin_meets_minimum_but_not_latest(tmp_path):
    (tmp_path / "settings.gradle").write_text(
        'plugins {\n    id "org.jetbrains.kotlin.android" version "2.0.0" apply false\n}\n'
    )
    result = check_kotlin_version(str(tmp_path))
    assert result["status"] == "update_available"
    assert result["detected"] == "2.0.0"
