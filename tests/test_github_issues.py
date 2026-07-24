import httpx

from flutter_stripe_mcp import github_issues
from flutter_stripe_mcp.github_issues import (
    _excerpt,
    _format_issue_detail,
    _format_search_results,
    _significant_words,
    get_issue,
    search_issues,
)

_API_BASE = "https://api.github.com"


def _client(handler):
    return httpx.Client(base_url=_API_BASE, transport=httpx.MockTransport(handler))


# --- pure parsing/formatting, no HTTP ---------------------------------------


def test_format_search_results_basic():
    raw = {
        "total_count": 2,
        "items": [
            {
                "number": 101,
                "title": "PaymentSheet crashes on Android 14",
                "state": "closed",
                "html_url": "https://github.com/flutter-stripe/flutter_stripe/issues/101",
                "body": "Steps to reproduce...",
            },
            {
                "number": 202,
                "title": "iOS build fails",
                "state": "open",
                "html_url": "https://github.com/flutter-stripe/flutter_stripe/issues/202",
                "body": None,
            },
        ],
    }
    result = _format_search_results(raw, limit=10)
    assert result["total_count"] == 2
    assert result["results"][0] == {
        "number": 101,
        "title": "PaymentSheet crashes on Android 14",
        "state": "closed",
        "url": "https://github.com/flutter-stripe/flutter_stripe/issues/101",
        "excerpt": "Steps to reproduce...",
    }
    assert result["results"][1]["excerpt"] == ""


def test_format_search_results_respects_limit():
    raw = {
        "total_count": 3,
        "items": [
            {"number": i, "title": "t", "state": "open", "html_url": "u", "body": "b"}
            for i in range(3)
        ],
    }
    result = _format_search_results(raw, limit=2)
    assert len(result["results"]) == 2


def test_excerpt_truncates_long_body():
    body = "word " * 100
    excerpt = _excerpt(body)
    assert len(excerpt) <= 303
    assert excerpt.endswith("...")


def test_excerpt_handles_empty_or_none_body():
    assert _excerpt("") == ""


def test_format_issue_detail_basic():
    issue_raw = {
        "number": 42,
        "title": "Crash on init",
        "state": "closed",
        "html_url": "https://github.com/flutter-stripe/flutter_stripe/issues/42",
        "body": "It crashes when...",
    }
    comments_raw = [
        {"user": {"login": "maintainer"}, "body": "Fixed by upgrading Kotlin to 1.9.0"},
    ]
    result = _format_issue_detail(issue_raw, comments_raw)
    assert result["number"] == 42
    assert result["comments"] == [
        {"author": "maintainer", "body": "Fixed by upgrading Kotlin to 1.9.0"}
    ]


# --- HTTP layer, via httpx.MockTransport ------------------------------------


def test_search_issues_success():
    def handler(request):
        assert request.url.path == "/search/issues"
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "number": 5,
                        "title": "PaymentSheet crash",
                        "state": "open",
                        "html_url": "https://github.com/flutter-stripe/flutter_stripe/issues/5",
                        "body": "crash log here",
                    }
                ],
            },
        )

    result = search_issues("PaymentSheet crash", client=_client(handler))
    assert result["total_count"] == 1
    assert result["results"][0]["number"] == 5


def test_search_issues_state_open_adds_qualifier():
    captured = {}

    def handler(request):
        captured["q"] = request.url.params["q"]
        return httpx.Response(200, json={"total_count": 0, "items": []})

    search_issues("crash", state="open", client=_client(handler))
    assert "state:open" in captured["q"]


def test_search_issues_state_all_omits_qualifier():
    captured = {}

    def handler(request):
        captured["q"] = request.url.params["q"]
        return httpx.Response(200, json={"total_count": 0, "items": []})

    search_issues("crash", state="all", client=_client(handler))
    assert "state:" not in captured["q"]


def test_search_issues_invalid_state_no_request():
    def handler(request):
        raise AssertionError("should not make a request for invalid state")

    result = search_issues("crash", state="bogus", client=_client(handler))
    assert result == {"error": "Invalid state 'bogus', must be one of: all, open, closed"}


def test_get_issue_success_with_comments():
    def handler(request):
        if request.url.path == "/repos/flutter-stripe/flutter_stripe/issues/7":
            return httpx.Response(
                200,
                json={
                    "number": 7,
                    "title": "Bug",
                    "state": "closed",
                    "html_url": "https://github.com/flutter-stripe/flutter_stripe/issues/7",
                    "body": "Description",
                },
            )
        assert request.url.path == "/repos/flutter-stripe/flutter_stripe/issues/7/comments"
        return httpx.Response(
            200,
            json=[{"user": {"login": "alice"}, "body": "Try this workaround"}],
        )

    result = get_issue(7, client=_client(handler))
    assert result["number"] == 7
    assert result["comments"] == [{"author": "alice", "body": "Try this workaround"}]
    assert "note" not in result


def test_get_issue_requests_up_to_100_comments_per_page():
    captured = {}

    def handler(request):
        if request.url.path.endswith("/comments"):
            captured["per_page"] = request.url.params["per_page"]
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={"number": 7, "title": "Bug", "state": "open", "html_url": "u", "body": "d"},
        )

    get_issue(7, client=_client(handler))
    assert captured["per_page"] == "100"


def test_get_issue_notes_truncation_when_more_comments_exist():
    def handler(request):
        if request.url.path.endswith("/comments"):
            return httpx.Response(
                200,
                json=[{"user": {"login": "alice"}, "body": "first page"}],
                headers={
                    "Link": '<https://api.github.com/x?page=2>; rel="next", '
                    '<https://api.github.com/x?page=3>; rel="last"'
                },
            )
        return httpx.Response(
            200,
            json={"number": 7, "title": "Bug", "state": "open", "html_url": "u", "body": "d"},
        )

    result = get_issue(7, client=_client(handler))
    assert "Showing the first 1 comments" in result["note"]


def test_get_issue_not_found_404():
    def handler(request):
        return httpx.Response(404, json={"message": "Not Found"})

    result = get_issue(999999, client=_client(handler))
    assert result["kind"] == "not_found"


def test_search_issues_rate_limited_403():
    def handler(request):
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1234567890"},
            json={"message": "rate limit exceeded"},
        )

    result = search_issues("crash", client=_client(handler))
    assert result["kind"] == "rate_limited"
    assert result["reset_at"] == "1234567890"


def test_search_issues_rate_limited_429():
    def handler(request):
        return httpx.Response(429, json={"message": "secondary rate limit"})

    result = search_issues("crash", client=_client(handler))
    assert result["kind"] == "rate_limited"


def test_network_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    result = search_issues("crash", client=_client(handler))
    assert result["kind"] == "network_error"


def test_malformed_json_response():
    def handler(request):
        return httpx.Response(200, text="not json")

    result = search_issues("crash", client=_client(handler))
    assert result["kind"] == "malformed_response"


# --- broadened (OR fallback) search -----------------------------------------


def test_significant_words_filters_stopwords_and_caps():
    words = _significant_words("kgp plugin build failure with the gradle sync", limit=6)
    assert "with" not in words
    assert "the" not in words
    assert len(words) <= 6
    assert words[:2] == ["kgp", "plugin"]


def test_search_issues_broadens_when_exact_match_is_empty():
    calls = []

    def handler(request):
        q = request.url.params["q"]
        calls.append(q)
        if " OR " in q:
            return httpx.Response(
                200,
                json={
                    "total_count": 1,
                    "items": [
                        {
                            "number": 9,
                            "title": "Flutter KGP ending",
                            "state": "closed",
                            "html_url": "https://github.com/flutter-stripe/flutter_stripe/issues/9",
                            "body": "kgp related",
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"total_count": 0, "items": []})

    result = search_issues("kgp plugin build failure", client=_client(handler))
    assert len(calls) == 2
    assert " OR " in calls[1]
    assert result["broadened_search"] is True
    assert "note" in result
    assert result["results"][0]["number"] == 9


def test_search_issues_no_broadening_when_exact_match_has_results():
    calls = []

    def handler(request):
        calls.append(request.url.params["q"])
        return httpx.Response(
            200,
            json={
                "total_count": 1,
                "items": [
                    {
                        "number": 1,
                        "title": "t",
                        "state": "open",
                        "html_url": "u",
                        "body": "b",
                    }
                ],
            },
        )

    result = search_issues("kgp plugin build failure", client=_client(handler))
    assert len(calls) == 1
    assert "broadened_search" not in result


def test_search_issues_no_broadening_for_single_word_query():
    calls = []

    def handler(request):
        calls.append(request.url.params["q"])
        return httpx.Response(200, json={"total_count": 0, "items": []})

    result = search_issues("kgp", client=_client(handler))
    assert len(calls) == 1
    assert result["total_count"] == 0
    assert "broadened_search" not in result


def test_search_issues_stays_empty_when_broadened_also_empty():
    calls = []

    def handler(request):
        calls.append(request.url.params["q"])
        return httpx.Response(200, json={"total_count": 0, "items": []})

    result = search_issues("kgp plugin build failure", client=_client(handler))
    assert len(calls) == 2
    assert result["total_count"] == 0
    assert "broadened_search" not in result


# --- optional GITHUB_TOKEN auth ---------------------------------------------


def test_no_authorization_header_without_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"total_count": 0, "items": []})

    search_issues("crash", client=_client(handler))
    assert captured["auth"] is None


def test_authorization_header_added_when_github_token_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-123")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"total_count": 0, "items": []})

    search_issues("crash", client=_client(handler))
    assert captured["auth"] == "Bearer test-token-123"


def test_rate_limited_message_omits_unauthenticated_hint_when_token_set(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-123")

    def handler(request):
        return httpx.Response(
            403,
            headers={"X-RateLimit-Remaining": "0"},
            json={"message": "rate limit exceeded"},
        )

    result = search_issues("crash", client=_client(handler))
    assert result["kind"] == "rate_limited"
    assert "GITHUB_TOKEN" not in result["error"]


# --- default (non-injected) client reuse ------------------------------------


def test_default_client_is_a_reused_singleton():
    a = github_issues._default_client()
    b = github_issues._default_client()
    assert a is b


def test_get_issue_reuses_default_client_when_none_injected(monkeypatch):
    request_paths = []

    def handler(request):
        request_paths.append(request.url.path)
        if request.url.path.endswith("/comments"):
            return httpx.Response(200, json=[])
        return httpx.Response(
            200,
            json={"number": 7, "title": "Bug", "state": "open", "html_url": "u", "body": "d"},
        )

    shared_client = _client(handler)
    monkeypatch.setattr(github_issues, "_default_client", lambda: shared_client)

    result = github_issues.get_issue(7)

    assert result["number"] == 7
    assert request_paths == [
        "/repos/flutter-stripe/flutter_stripe/issues/7",
        "/repos/flutter-stripe/flutter_stripe/issues/7/comments",
    ]
