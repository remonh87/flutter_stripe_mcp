import asyncio

from flutter_stripe_mcp import server


def test_search_flutter_stripe_issues_forwards_args(monkeypatch):
    captured = {}

    def fake_search_issues(query, state="all", limit=10):
        captured.update(query=query, state=state, limit=limit)
        return {"total_count": 0, "results": []}

    monkeypatch.setattr(server, "search_issues", fake_search_issues)

    result = asyncio.run(
        server.search_flutter_stripe_issues("crash", state="open", limit=5)
    )

    assert captured == {"query": "crash", "state": "open", "limit": 5}
    assert result == {"total_count": 0, "results": []}


def test_get_flutter_stripe_issue_forwards_issue_number(monkeypatch):
    captured = {}

    def fake_get_issue(issue_number):
        captured["issue_number"] = issue_number
        return {"number": issue_number}

    monkeypatch.setattr(server, "get_issue", fake_get_issue)

    result = asyncio.run(server.get_flutter_stripe_issue(42))

    assert captured == {"issue_number": 42}
    assert result == {"number": 42}
