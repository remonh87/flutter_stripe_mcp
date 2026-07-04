import glob
import os
import re
import xml.etree.ElementTree as ET
from typing import Any

KOTLIN_MIN_VERSION = "1.9.0"
KOTLIN_LATEST_VERSION = "2.1.21"

GRADLE_WRAPPER_MIN_VERSION = "8.0"

IOS_MIN_DEPLOYMENT_TARGET = "13.0"

VALID_THEME_PARENT_PREFIXES: tuple[str, ...] = (
    "Theme.AppCompat",
    "Base.Theme.AppCompat",
    "Theme.MaterialComponents",
    "Theme.Material3",
)

# Modern Flutter templates declare the Kotlin plugin version in settings.gradle;
# legacy templates use ext.kotlin_version in the project-level build.gradle.
_GRADLE_FILE_CANDIDATES: tuple[str, ...] = (
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
)

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


def check_kotlin_version(android_path: str) -> dict[str, Any]:
    searched: list[str] = []
    for name in _GRADLE_FILE_CANDIDATES:
        path = os.path.join(android_path, name)
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            continue
        searched.append(name)
        for pattern in _KOTLIN_VERSION_PATTERNS:
            match = pattern.search(content)
            if match:
                return _kotlin_version_result(match.group(1), path)

    if not searched:
        return {
            "status": "missing",
            "fix": f"No settings.gradle or build.gradle (or .kts) found under {android_path}.",
        }
    return {
        "status": "missing",
        "fix": (
            f"No Kotlin version detected in {', '.join(searched)} under {android_path}. "
            f'Add to the settings.gradle plugins block: id "org.jetbrains.kotlin.android" '
            f'version "{KOTLIN_LATEST_VERSION}" apply false '
            f"(or ext.kotlin_version = '{KOTLIN_LATEST_VERSION}' in legacy build.gradle)."
        ),
    }


def _kotlin_version_result(detected: str, file_path: str) -> dict[str, Any]:
    detected_t = _parse_version(detected)
    if detected_t < _parse_version(KOTLIN_MIN_VERSION):
        return {
            "status": "outdated",
            "detected": detected,
            "fix": (
                f"Kotlin {detected} (in {file_path}) is below the minimum "
                f"{KOTLIN_MIN_VERSION} required by flutter_stripe. Update to {KOTLIN_LATEST_VERSION}."
            ),
        }
    if detected_t < _parse_version(KOTLIN_LATEST_VERSION):
        return {
            "status": "update_available",
            "detected": detected,
            "fix": (
                f"Kotlin {detected} (in {file_path}) meets the minimum ({KOTLIN_MIN_VERSION}) "
                f"but {KOTLIN_LATEST_VERSION} is the latest recommended version."
            ),
        }
    return {"status": "ok"}


_GRADLE_WRAPPER_VERSION_PATTERN = re.compile(
    r"distributionUrl=.*gradle-(\d+\.\d+(?:\.\d+)?)-(?:all|bin)\.zip"
)


def check_gradle_wrapper_version(gradle_wrapper_path: str) -> dict[str, Any]:
    try:
        with open(gradle_wrapper_path, encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        return {"status": "missing", "fix": f"File not found: {gradle_wrapper_path}"}
    except OSError as exc:
        return {"status": "error", "fix": f"Could not read file: {exc}"}

    match = _GRADLE_WRAPPER_VERSION_PATTERN.search(content)
    if not match:
        return {
            "status": "missing",
            "fix": f"Could not detect Gradle version in {gradle_wrapper_path}.",
        }

    detected = match.group(1)
    if _parse_version(detected) >= _parse_version(GRADLE_WRAPPER_MIN_VERSION):
        return {"status": "ok"}
    return {
        "status": "outdated",
        "detected": detected,
        "fix": (
            f"Gradle {detected} is below the minimum {GRADLE_WRAPPER_MIN_VERSION} required. "
            f"Update the distributionUrl in {gradle_wrapper_path} to use Gradle 8+."
        ),
    }


def check_android_themes(android_src_path: str) -> dict[str, Any]:
    try:
        patterns = [
            os.path.join(android_src_path, "**", "res", "values*", "styles.xml"),
            os.path.join(android_src_path, "**", "res", "values*", "themes.xml"),
        ]
        files = sorted(set(f for p in patterns for f in glob.glob(p, recursive=True)))

        if not files:
            return {
                "status": "missing",
                "fix": f"No styles.xml or themes.xml found under {android_src_path}.",
            }

        violations: list[str] = []
        for file_path in files:
            try:
                root = ET.parse(file_path).getroot()
            except (ET.ParseError, OSError):
                continue
            for elem in root.findall("style"):
                name = elem.get("name", "")
                if "theme" not in name.lower():
                    continue
                parent = elem.get("parent", "")
                parent_clean = parent[len("@style/"):] if parent.startswith("@style/") else parent
                if not any(parent_clean.startswith(p) for p in VALID_THEME_PARENT_PREFIXES):
                    violations.append(f"{file_path}: style '{name}' has parent '{parent}'")

        if violations:
            lines = "\n".join(f"  {v}" for v in violations)
            return {
                "status": "invalid_theme_parent",
                "fix": (
                    "All theme styles must derive from Theme.AppCompat.*, "
                    "Theme.MaterialComponents.*, or Theme.Material3.*. Fix these:\n" + lines
                ),
            }
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "fix": f"Unexpected error scanning themes: {exc}"}


_MAIN_ACTIVITY_KOTLIN_PATTERN = re.compile(
    r"class\s+MainActivity\s*(?:\([^)]*\))?\s*:\s*([A-Za-z0-9_]+)"
)
_MAIN_ACTIVITY_JAVA_PATTERN = re.compile(
    r"class\s+MainActivity\s+extends\s+([A-Za-z0-9_]+)"
)
_FLUTTER_FRAGMENT_ACTIVITY = "FlutterFragmentActivity"


def check_main_activity(android_src_path: str) -> dict[str, Any]:
    try:
        files = sorted(
            f
            for ext in ("*.kt", "*.java")
            for f in glob.glob(
                os.path.join(android_src_path, "**", "MainActivity" + ext[1:]),
                recursive=True,
            )
        )

        if not files:
            return {
                "status": "missing",
                "fix": (
                    f"No MainActivity.kt or MainActivity.java found under {android_src_path}."
                ),
            }

        violations: list[str] = []
        for file_path in files:
            try:
                content = open(file_path, encoding="utf-8").read()
            except OSError as exc:
                violations.append(f"{file_path}: unreadable ({exc})")
                continue

            pattern = (
                _MAIN_ACTIVITY_KOTLIN_PATTERN
                if file_path.endswith(".kt")
                else _MAIN_ACTIVITY_JAVA_PATTERN
            )
            match = pattern.search(content)
            if not match:
                violations.append(f"{file_path}: could not detect base class")
            elif match.group(1) != _FLUTTER_FRAGMENT_ACTIVITY:
                violations.append(f"{file_path}: extends {match.group(1)}")

        if violations:
            lines = "\n".join(f"  {v}" for v in violations)
            return {
                "status": "wrong_base_class",
                "fix": (
                    f"MainActivity must extend {_FLUTTER_FRAGMENT_ACTIVITY} "
                    f"(not FlutterActivity). Fix these:\n{lines}\n"
                    "See: https://github.com/flutter-stripe/flutter_stripe#android"
                ),
            }
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "fix": f"Unexpected error scanning MainActivity: {exc}"}


_PROGUARD_REFERENCE_URL = (
    "https://raw.githubusercontent.com/flutter-stripe/flutter_stripe/main"
    "/example/android/app/proguard-rules.pro"
)

_PROGUARD_REQUIRED_RULES: list[str] = [
    "-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivity$g",
    "-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivityStarter$Args",
    "-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivityStarter$Error",
    "-dontwarn com.stripe.android.pushProvisioning.PushProvisioningActivityStarter",
    "-dontwarn com.stripe.android.pushProvisioning.PushProvisioningEphemeralKeyProvider",
    "-dontwarn kotlinx.parcelize.Parceler$DefaultImpls",
    "-dontwarn kotlinx.parcelize.Parceler",
    "-dontwarn kotlinx.parcelize.Parcelize",
    "-keep class com.stripe.** { *; }",
]


def _parse_proguard_rules(content: str) -> list[str]:
    return [
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def check_proguard_rules(android_app_path: str) -> dict[str, Any]:
    local_path = os.path.join(android_app_path, "proguard-rules.pro")

    try:
        with open(local_path, encoding="utf-8") as fh:
            local_content = fh.read()
    except FileNotFoundError:
        return {
            "status": "missing",
            "fix": (
                f"proguard-rules.pro not found at {local_path}. "
                f"Create it with the required Stripe rules from: {_PROGUARD_REFERENCE_URL}"
            ),
        }
    except OSError as exc:
        return {"status": "error", "fix": f"Could not read {local_path}: {exc}"}

    local_rules = set(_parse_proguard_rules(local_content))
    missing = [rule for rule in _PROGUARD_REQUIRED_RULES if rule not in local_rules]

    if missing:
        lines = "\n".join(f"  {r}" for r in missing)
        return {
            "status": "missing_rules",
            "fix": (
                f"proguard-rules.pro is missing {len(missing)} required Stripe rule(s). "
                f"Add the following to {local_path}:\n{lines}\n"
                f"Full reference: {_PROGUARD_REFERENCE_URL}"
            ),
        }
    return {"status": "ok"}


_PODFILE_PLATFORM_PATTERN = re.compile(
    r"platform\s*:ios\s*,\s*['\"](\d+(?:\.\d+)?)['\"]"
)
_PBXPROJ_DEPLOYMENT_TARGET_PATTERN = re.compile(
    r"IPHONEOS_DEPLOYMENT_TARGET\s*=\s*(\d+(?:\.\d+)?)"
)


def check_ios_deployment_target(ios_path: str) -> dict[str, Any]:
    source: str | None = None
    detected: str | None = None

    podfile_path = os.path.join(ios_path, "Podfile")
    try:
        with open(podfile_path, encoding="utf-8") as fh:
            content = fh.read()
        match = _PODFILE_PLATFORM_PATTERN.search(content)
        if match:
            detected = match.group(1)
            source = "podfile"
    except FileNotFoundError:
        pass
    except OSError as exc:
        return {"status": "error", "fix": f"Could not read Podfile: {exc}"}

    if detected is None:
        pbxproj_path = os.path.join(ios_path, "Runner.xcodeproj", "project.pbxproj")
        try:
            with open(pbxproj_path, encoding="utf-8") as fh:
                content = fh.read()
            versions = _PBXPROJ_DEPLOYMENT_TARGET_PATTERN.findall(content)
            if versions:
                detected = min(versions, key=_parse_version)
                source = "pbxproj"
        except FileNotFoundError:
            pass
        except OSError as exc:
            return {"status": "error", "fix": f"Could not read project.pbxproj: {exc}"}

    if detected is None:
        return {
            "status": "missing",
            "fix": (
                "Could not detect the iOS minimum deployment target. "
                f"For CocoaPods, add \"platform :ios, '{IOS_MIN_DEPLOYMENT_TARGET}'\" to your Podfile. "
                "For SPM, open Xcode → select the Runner target → Build Settings → "
                f"set 'iOS Deployment Target' to {IOS_MIN_DEPLOYMENT_TARGET}."
            ),
        }

    if _parse_version(detected) >= _parse_version(IOS_MIN_DEPLOYMENT_TARGET):
        return {"status": "ok"}

    if source == "podfile":
        how = f"Update your Podfile: platform :ios, '{IOS_MIN_DEPLOYMENT_TARGET}'"
    else:
        how = (
            f"In Xcode, select the Runner target → Build Settings → "
            f"set 'iOS Deployment Target' to {IOS_MIN_DEPLOYMENT_TARGET}."
        )
    return {
        "status": "outdated",
        "detected": detected,
        "fix": (
            f"iOS deployment target {detected} is below the minimum "
            f"{IOS_MIN_DEPLOYMENT_TARGET} required by flutter_stripe. {how}"
        ),
    }


def check_ios_camera_permission(ios_path: str) -> dict[str, Any]:
    info_plist_path = os.path.join(ios_path, "Runner", "Info.plist")

    try:
        tree = ET.parse(info_plist_path)
    except FileNotFoundError:
        return {"status": "missing", "fix": f"Info.plist not found at {info_plist_path}."}
    except (ET.ParseError, OSError) as exc:
        return {"status": "error", "fix": f"Could not read Info.plist: {exc}"}

    plist_dict = tree.getroot().find("dict")
    keys: list[str] = (
        [elem.text or "" for elem in plist_dict.findall("key")]
        if plist_dict is not None
        else []
    )
    if "NSCameraUsageDescription" in keys:
        return {"status": "ok"}
    return {
        "status": "suggestion",
        "fix": (
            "NSCameraUsageDescription is not set in ios/Runner/Info.plist. "
            "Add it if your app uses card scanning (e.g. flutter_stripe's CardField). "
            "Example: <key>NSCameraUsageDescription</key>"
            "<string>Used to scan payment cards</string>"
        ),
    }
