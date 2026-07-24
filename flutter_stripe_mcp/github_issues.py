import atexit
import os
import re
import threading
from typing import Any, Literal

import httpx

_API_BASE = "https://api.github.com"
_REPO = "flutter-stripe/flutter_stripe"
_USER_AGENT = "flutter-stripe-mcp"
_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": _USER_AGENT,
    "X-GitHub-Api-Version": "2022-11-28",
}

# GitHub's search API rejects a query with more than 5 AND/OR/NOT operators,
# so an OR'd fallback query can use at most 6 terms.
_MAX_OR_TERMS = 6
_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "at", "for", "with", "and", "or", "not",
    "this", "that", "it", "its", "as", "by", "from", "when", "while", "i",
}


_default_client_instance: httpx.Client | None = None
_default_client_lock = threading.Lock()


def _default_client() -> httpx.Client:
    """The process-lifetime httpx.Client used when no client is injected.

    Reused across calls (and across tool invocations) so requests share
    connection pooling/keep-alive instead of paying a fresh TCP+TLS
    handshake per GitHub API call.
    """
    global _default_client_instance
    if _default_client_instance is None:
        with _default_client_lock:
            if _default_client_instance is None:
                _default_client_instance = httpx.Client(base_url=_API_BASE)
    return _default_client_instance


@atexit.register
def _close_default_client() -> None:
    if _default_client_instance is not None:
        _default_client_instance.close()


def _github_token() -> str | None:
    """Optional token from GITHUB_TOKEN/GH_TOKEN, to raise the rate limit
    from 60/hour (unauthenticated) to 5,000/hour. Not required."""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _request_headers() -> dict[str, str]:
    headers = dict(_HEADERS)
    token = _github_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _significant_words(text: str, limit: int) -> list[str]:
    """Extract up to `limit` distinct, non-stopword words from free text."""
    words = re.findall(r"[A-Za-z0-9]+", text)
    seen: list[str] = []
    seen_lower: set[str] = set()
    for word in words:
        lower = word.lower()
        if lower in _STOPWORDS or lower in seen_lower:
            continue
        seen.append(word)
        seen_lower.add(lower)
        if len(seen) >= limit:
            break
    return seen


def _get_response(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    client: httpx.Client | None = None,
) -> tuple[httpx.Response | None, dict[str, Any] | None]:
    """GET a GitHub API path. Returns (response, error_dict); exactly one is None."""
    headers = _request_headers()
    active_client = client if client is not None else _default_client()
    try:
        response = active_client.get(path, params=params, headers=headers, timeout=10.0)
    except httpx.RequestError as exc:
        return None, {
            "error": f"Network error contacting GitHub API: {exc}",
            "kind": "network_error",
        }

    if response.status_code == 404:
        return None, {
            "error": f"GitHub API returned 404 for {path}",
            "kind": "not_found",
        }

    is_rate_limited = response.status_code == 429 or (
        response.status_code == 403
        and response.headers.get("X-RateLimit-Remaining") == "0"
    )
    if is_rate_limited:
        if _github_token():
            message = "GitHub API rate limit exceeded. Wait for the limit to reset and try again."
        else:
            message = (
                "GitHub API rate limit exceeded (60 requests/hour, unauthenticated). "
                "Set a GITHUB_TOKEN environment variable to raise this to 5,000/hour, "
                "or wait for the limit to reset."
            )
        error: dict[str, Any] = {"error": message, "kind": "rate_limited"}
        reset_header = response.headers.get("X-RateLimit-Reset")
        if reset_header is not None:
            error["reset_at"] = reset_header
        return None, error

    if not (200 <= response.status_code < 300):
        return None, {
            "error": f"GitHub API returned HTTP {response.status_code}: {response.text[:200]}",
            "kind": "http_error",
        }

    return response, None


def _request(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    client: httpx.Client | None = None,
) -> tuple[Any, dict[str, Any] | None]:
    """GET a GitHub API path and parse its JSON body. Returns (json_body, error_dict)."""
    response, err = _get_response(path, params, client=client)
    if err is not None:
        return None, err

    try:
        return response.json(), None
    except ValueError:
        return None, {
            "error": "Received malformed (non-JSON) response from GitHub API",
            "kind": "malformed_response",
        }


def _build_search_query(
    query: str, state: Literal["all", "open", "closed"], *, broaden: bool = False
) -> str:
    """Build the GitHub search `q` string.

    Plain space-separated terms are implicitly ANDed by GitHub's search API,
    so a multi-word query only matches issues containing every literal word.
    When `broaden` is set, terms are OR'd instead, so any one of them matching
    is enough - used as a fallback when the exact-match search finds nothing.
    """
    if broaden:
        words = _significant_words(query, _MAX_OR_TERMS)
        terms = " OR ".join(words) if words else query
    else:
        terms = query
    q = f"repo:{_REPO} is:issue {terms}"
    if state in ("open", "closed"):
        q += f" state:{state}"
    return q


def _fetch_search_issues(
    query: str,
    state: Literal["all", "open", "closed"],
    limit: int,
    *,
    broaden: bool = False,
    client: httpx.Client | None = None,
) -> tuple[Any, dict[str, Any] | None]:
    q = _build_search_query(query, state, broaden=broaden)
    return _request("/search/issues", {"q": q, "per_page": limit}, client=client)


def _fetch_issue(
    issue_number: int, *, client: httpx.Client | None = None
) -> tuple[Any, dict[str, Any] | None]:
    return _request(f"/repos/{_REPO}/issues/{issue_number}", client=client)


def _fetch_issue_comments(
    issue_number: int, *, client: httpx.Client | None = None
) -> tuple[Any, dict[str, Any] | None, bool]:
    """GET an issue's comments (up to 100). Returns (comments, error, truncated),
    where `truncated` is True if GitHub reports more comments beyond this page."""
    response, err = _get_response(
        f"/repos/{_REPO}/issues/{issue_number}/comments",
        {"per_page": 100},
        client=client,
    )
    if err is not None:
        return None, err, False

    truncated = 'rel="next"' in response.headers.get("Link", "")
    try:
        return response.json(), None, truncated
    except ValueError:
        return (
            None,
            {
                "error": "Received malformed (non-JSON) response from GitHub API",
                "kind": "malformed_response",
            },
            False,
        )


def _excerpt(body: str, max_len: int = 300) -> str:
    collapsed = re.sub(r"\s+", " ", body).strip()
    if len(collapsed) <= max_len:
        return collapsed
    return collapsed[:max_len].rstrip() + "..."


def _format_search_results(raw: dict[str, Any], limit: int) -> dict[str, Any]:
    items = raw.get("items", [])[:limit]
    return {
        "total_count": raw.get("total_count", 0),
        "results": [
            {
                "number": item["number"],
                "title": item["title"],
                "state": item["state"],
                "url": item["html_url"],
                "excerpt": _excerpt(item.get("body") or ""),
            }
            for item in items
        ],
    }


def _format_issue_detail(
    issue_raw: dict[str, Any], comments_raw: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "number": issue_raw["number"],
        "title": issue_raw["title"],
        "state": issue_raw["state"],
        "url": issue_raw["html_url"],
        "body": issue_raw.get("body") or "",
        "comments": [
            {"author": c["user"]["login"], "body": c.get("body") or ""}
            for c in comments_raw
        ],
    }


def search_issues(
    query: str,
    state: Literal["all", "open", "closed"] = "all",
    limit: int = 10,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Search issues in flutter-stripe/flutter_stripe.

    GitHub's search ANDs space-separated words together, so a multi-word
    query only matches issues containing every literal word. If that exact
    search finds nothing, this automatically retries with the significant
    words OR'd together instead (any one matching is enough) and marks the
    result with "broadened_search": true so callers know it's a looser match.

    Args:
        query: Free-text search terms.
        state: "all", "open", or "closed".
        limit: Max number of results (clamped to 1-30).
        client: Optional injected httpx.Client, for tests only.

    Returns:
        {"total_count": int, "results": [{"number", "title", "state", "url", "excerpt"}]}
        (plus "broadened_search" and "note" if the fallback search was used),
        or {"error": "...", "kind": "..."} on failure.
    """
    if state not in ("all", "open", "closed"):
        return {"error": f"Invalid state '{state}', must be one of: all, open, closed"}
    limit = max(1, min(limit, 30))

    raw, err = _fetch_search_issues(query, state, limit, client=client)
    if err is not None:
        return err
    result = _format_search_results(raw, limit)
    if result["total_count"] > 0:
        return result

    words = _significant_words(query, _MAX_OR_TERMS)
    if len(words) < 2:
        return result

    broadened_raw, err = _fetch_search_issues(
        query, state, limit, broaden=True, client=client
    )
    if err is not None:
        return result
    broadened_result = _format_search_results(broadened_raw, limit)
    if broadened_result["total_count"] == 0:
        return result

    broadened_result["broadened_search"] = True
    broadened_result["note"] = (
        "No issues matched all of the search terms; showing broader results "
        "matching any of: " + ", ".join(words)
    )
    return broadened_result


def get_issue(issue_number: int, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Fetch one issue's full body and comments from flutter-stripe/flutter_stripe.

    Args:
        issue_number: The GitHub issue number.
        client: Optional injected httpx.Client, for tests only.

    Returns:
        {"number", "title", "state", "url", "body", "comments": [{"author", "body"}]}
        (plus "note" if the comment thread was too long to fetch in full),
        or {"error": "...", "kind": "..."} on failure.
    """
    issue_raw, err = _fetch_issue(issue_number, client=client)
    if err is not None:
        return err

    comments_raw, err, truncated = _fetch_issue_comments(issue_number, client=client)
    if err is not None:
        return err

    result = _format_issue_detail(issue_raw, comments_raw)
    if truncated:
        result["note"] = (
            f"Showing the first {len(comments_raw)} comments; this issue has more "
            "that weren't fetched."
        )
    return result
