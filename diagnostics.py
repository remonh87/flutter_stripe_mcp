import glob
import os
import re
import urllib.error
import urllib.request
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


_GRADLE_WRAPPER_VERSION_PATTERN = re.compile(
    r"distributionUrl=.*gradle-(\d+\.\d+(?:\.\d+)?)-(?:all|bin)\.zip"
)


def check_gradle_wrapper_version(gradle_wrapper_path: str) -> dict[str, Any]:
    try:
        with open(gradle_wrapper_path, encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        return {
            "detected_version": None,
            "minimum_required": GRADLE_WRAPPER_MIN_VERSION,
            "meets_requirement": None,
            "status": "error",
            "suggestion": f"File not found: {gradle_wrapper_path}",
        }
    except OSError as exc:
        return {
            "detected_version": None,
            "minimum_required": GRADLE_WRAPPER_MIN_VERSION,
            "meets_requirement": None,
            "status": "error",
            "suggestion": f"Could not read file: {exc}",
        }

    match = _GRADLE_WRAPPER_VERSION_PATTERN.search(content)
    if not match:
        return {
            "detected_version": None,
            "minimum_required": GRADLE_WRAPPER_MIN_VERSION,
            "meets_requirement": False,
            "status": "missing",
            "suggestion": f"Could not detect Gradle version in {gradle_wrapper_path}.",
        }

    detected_version = match.group(1)
    meets = _parse_version(detected_version) >= _parse_version(GRADLE_WRAPPER_MIN_VERSION)
    return {
        "detected_version": detected_version,
        "minimum_required": GRADLE_WRAPPER_MIN_VERSION,
        "meets_requirement": meets,
        "status": "ok" if meets else "outdated",
        "suggestion": None if meets else (
            f"Gradle {detected_version} is below the minimum {GRADLE_WRAPPER_MIN_VERSION} "
            f"required. Update gradle-wrapper.properties to use Gradle 8+."
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
                "status": "no_files_found",
                "files_checked": 0,
                "violations": [],
                "suggestion": f"No styles.xml or themes.xml found under {android_src_path}.",
            }

        violations: list[dict[str, str]] = []
        files_checked = 0

        for file_path in files:
            try:
                root = ET.parse(file_path).getroot()
            except (ET.ParseError, OSError):
                continue

            files_checked += 1
            for elem in root.findall("style"):
                name = elem.get("name", "")
                if "theme" not in name.lower():
                    continue
                parent = elem.get("parent", "")
                parent_clean = parent[len("@style/"):] if parent.startswith("@style/") else parent
                if not any(parent_clean.startswith(p) for p in VALID_THEME_PARENT_PREFIXES):
                    violations.append({
                        "file": file_path,
                        "style_name": name,
                        "parent": parent,
                        "issue": (
                            f"Style '{name}' has parent '{parent}' which does not derive from "
                            f"Theme.AppCompat.*, Theme.MaterialComponents.*, or Theme.Material3.*."
                        ),
                    })

        status = "invalid_theme_parent" if violations else "ok"
        suggestion: str | None = None
        if violations:
            lines = "\n".join(f"  {v['file']}: {v['issue']}" for v in violations)
            suggestion = (
                "All theme styles must derive from Theme.AppCompat.*, "
                "Theme.MaterialComponents.*, or Theme.Material3.*. Found issues:\n" + lines
            )

        return {
            "status": status,
            "files_checked": files_checked,
            "violations": violations,
            "suggestion": suggestion,
        }
    except Exception as exc:
        return {
            "status": "error",
            "files_checked": 0,
            "violations": [],
            "suggestion": f"Unexpected error scanning themes: {exc}",
        }


_MAIN_ACTIVITY_KOTLIN_PATTERN = re.compile(
    r"class\s+MainActivity\s*(?:\([^)]*\))?\s*:\s*([A-Za-z0-9_]+)"
)
_MAIN_ACTIVITY_JAVA_PATTERN = re.compile(
    r"class\s+MainActivity\s+extends\s+([A-Za-z0-9_]+)"
)
_FLUTTER_FRAGMENT_ACTIVITY = "FlutterFragmentActivity"
_FLUTTER_ACTIVITY = "FlutterActivity"


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
                "status": "no_file_found",
                "files_checked": [],
                "violations": [],
                "suggestion": (
                    f"No MainActivity.kt or MainActivity.java found under {android_src_path}. "
                    "Ensure the path points to the Android app src directory."
                ),
            }

        violations: list[dict[str, str]] = []
        for file_path in files:
            try:
                content = open(file_path, encoding="utf-8").read()
            except OSError as exc:
                violations.append({"file": file_path, "found_base_class": f"unreadable: {exc}"})
                continue

            pattern = (
                _MAIN_ACTIVITY_KOTLIN_PATTERN
                if file_path.endswith(".kt")
                else _MAIN_ACTIVITY_JAVA_PATTERN
            )
            match = pattern.search(content)
            if not match:
                violations.append({
                    "file": file_path,
                    "found_base_class": "unknown (could not detect base class)",
                })
                continue

            base_class = match.group(1)
            if base_class != _FLUTTER_FRAGMENT_ACTIVITY:
                violations.append({"file": file_path, "found_base_class": base_class})

        if violations:
            lines = "\n".join(
                f"  {v['file']}: extends {v['found_base_class']}" for v in violations
            )
            suggestion = (
                f"MainActivity must extend {_FLUTTER_FRAGMENT_ACTIVITY} "
                f"(not {_FLUTTER_ACTIVITY}). Found issues:\n{lines}\n"
                "See: https://github.com/flutter-stripe/flutter_stripe#android"
            )
        else:
            suggestion = None

        return {
            "status": "wrong_base_class" if violations else "ok",
            "files_checked": files,
            "violations": violations,
            "suggestion": suggestion,
        }
    except Exception as exc:
        return {
            "status": "error",
            "files_checked": [],
            "violations": [],
            "suggestion": f"Unexpected error scanning MainActivity: {exc}",
        }


_PROGUARD_REFERENCE_URL = (
    "https://raw.githubusercontent.com/flutter-stripe/flutter_stripe/main"
    "/example/android/app/proguard-rules.pro"
)

_PROGUARD_FALLBACK_RULES: list[str] = [
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


_PODFILE_PLATFORM_PATTERN = re.compile(
    r"platform\s*:ios\s*,\s*['\"](\d+(?:\.\d+)?)['\"]"
)
_PBXPROJ_DEPLOYMENT_TARGET_PATTERN = re.compile(
    r"IPHONEOS_DEPLOYMENT_TARGET\s*=\s*(\d+(?:\.\d+)?)"
)


def check_ios_deployment_target(ios_path: str) -> dict[str, Any]:
    source: str | None = None
    detected_version: str | None = None

    podfile_path = os.path.join(ios_path, "Podfile")
    try:
        with open(podfile_path, encoding="utf-8") as fh:
            content = fh.read()
        match = _PODFILE_PLATFORM_PATTERN.search(content)
        if match:
            detected_version = match.group(1)
            source = "podfile"
    except FileNotFoundError:
        pass
    except OSError as exc:
        return {
            "detected_version": None,
            "minimum_required": IOS_MIN_DEPLOYMENT_TARGET,
            "meets_requirement": None,
            "source": "podfile",
            "status": "error",
            "suggestion": f"Could not read Podfile: {exc}",
        }

    if detected_version is None:
        pbxproj_path = os.path.join(ios_path, "Runner.xcodeproj", "project.pbxproj")
        try:
            with open(pbxproj_path, encoding="utf-8") as fh:
                content = fh.read()
            versions = _PBXPROJ_DEPLOYMENT_TARGET_PATTERN.findall(content)
            if versions:
                detected_version = min(versions, key=_parse_version)
                source = "pbxproj"
        except FileNotFoundError:
            pass
        except OSError as exc:
            return {
                "detected_version": None,
                "minimum_required": IOS_MIN_DEPLOYMENT_TARGET,
                "meets_requirement": None,
                "source": "pbxproj",
                "status": "error",
                "suggestion": f"Could not read project.pbxproj: {exc}",
            }

    if detected_version is None:
        return {
            "detected_version": None,
            "minimum_required": IOS_MIN_DEPLOYMENT_TARGET,
            "meets_requirement": None,
            "source": None,
            "status": "missing",
            "suggestion": (
                "Could not detect the iOS minimum deployment target. "
                "For CocoaPods, add \"platform :ios, '13.0'\" to your Podfile. "
                "For SPM, open Xcode → select the Runner target → Build Settings → "
                "set 'iOS Deployment Target' to 13.0."
            ),
        }

    meets = _parse_version(detected_version) >= _parse_version(IOS_MIN_DEPLOYMENT_TARGET)

    if meets:
        suggestion = None
    elif source == "podfile":
        suggestion = (
            f"iOS deployment target {detected_version} is below the minimum "
            f"{IOS_MIN_DEPLOYMENT_TARGET} required by flutter_stripe. "
            f"Update your Podfile: platform :ios, '{IOS_MIN_DEPLOYMENT_TARGET}'"
        )
    else:
        suggestion = (
            f"iOS deployment target {detected_version} is below the minimum "
            f"{IOS_MIN_DEPLOYMENT_TARGET} required by flutter_stripe. "
            f"In Xcode, select the Runner target → Build Settings → "
            f"set 'iOS Deployment Target' to {IOS_MIN_DEPLOYMENT_TARGET}."
        )

    return {
        "detected_version": detected_version,
        "minimum_required": IOS_MIN_DEPLOYMENT_TARGET,
        "meets_requirement": meets,
        "source": source,
        "status": "ok" if meets else "outdated",
        "suggestion": suggestion,
    }


def check_ios_camera_permission(ios_path: str) -> dict[str, Any]:
    info_plist_path = os.path.join(ios_path, "Runner", "Info.plist")

    try:
        tree = ET.parse(info_plist_path)
    except FileNotFoundError:
        return {
            "has_permission": None,
            "status": "error",
            "suggestion": f"Info.plist not found at {info_plist_path}.",
        }
    except ET.ParseError as exc:
        return {
            "has_permission": None,
            "status": "error",
            "suggestion": f"Could not parse Info.plist: {exc}",
        }
    except OSError as exc:
        return {
            "has_permission": None,
            "status": "error",
            "suggestion": f"Could not read Info.plist: {exc}",
        }

    root = tree.getroot()
    plist_dict = root.find("dict")
    keys: list[str] = (
        [elem.text or "" for elem in plist_dict.findall("key")]
        if plist_dict is not None
        else []
    )
    has_permission = "NSCameraUsageDescription" in keys

    return {
        "has_permission": has_permission,
        "status": "ok" if has_permission else "suggestion",
        "suggestion": None if has_permission else (
            "NSCameraUsageDescription is not set in ios/Runner/Info.plist. "
            "Add it if your app uses card scanning (e.g. flutter_stripe's CardField). "
            "Example: <key>NSCameraUsageDescription</key>"
            "<string>Used to scan payment cards</string>"
        ),
    }


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
            "status": "no_file_found",
            "source": None,
            "missing_rules": [],
            "reference_url": _PROGUARD_REFERENCE_URL,
            "suggestion": (
                f"proguard-rules.pro not found at {local_path}. "
                f"Create it with the required Stripe rules from: {_PROGUARD_REFERENCE_URL}"
            ),
        }
    except OSError as exc:
        return {
            "status": "error",
            "source": None,
            "missing_rules": [],
            "reference_url": _PROGUARD_REFERENCE_URL,
            "suggestion": f"Could not read {local_path}: {exc}",
        }

    local_rules = set(_parse_proguard_rules(local_content))

    # Try online reference first
    try:
        with urllib.request.urlopen(_PROGUARD_REFERENCE_URL, timeout=5) as resp:
            reference_content = resp.read().decode("utf-8")
        required_rules = _parse_proguard_rules(reference_content)
        source = "online"
    except (urllib.error.URLError, OSError):
        required_rules = _PROGUARD_FALLBACK_RULES
        source = "fallback"

    missing = [rule for rule in required_rules if rule not in local_rules]

    if missing:
        lines = "\n".join(f"  {r}" for r in missing)
        suggestion = (
            f"proguard-rules.pro is missing {len(missing)} required Stripe rule(s). "
            f"Add the following to {local_path}:\n{lines}\n"
            f"Full reference: {_PROGUARD_REFERENCE_URL}"
        )
        status = "missing_rules"
    else:
        suggestion = None
        status = "ok"

    return {
        "status": status,
        "source": source,
        "missing_rules": missing,
        "reference_url": _PROGUARD_REFERENCE_URL,
        "suggestion": suggestion,
    }
