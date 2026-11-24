

def test_gh_json_surfaces_stderr_after_retries(monkeypatch):
    import subprocess as sp

    from verify import full_verify

    calls = {"n": 0}

    def fake_run(cmd, capture_output, text):
        calls["n"] += 1
        return sp.CompletedProcess(cmd, 1, stdout="", stderr="HTTP 502: boom")

    monkeypatch.setattr(full_verify.subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda s: None)
    try:
        full_verify.gh_json(["graphql", "-f", "query=x"], retries=2)
        raise AssertionError("expected GhError")
    except full_verify.GhError as exc:
        assert "HTTP 502: boom" in str(exc)
    assert calls["n"] == 3  # initial + 2 retries


def test_gh_json_retries_then_succeeds(monkeypatch):
    import subprocess as sp

    from verify import full_verify

    calls = {"n": 0}

    def fake_run(cmd, capture_output, text):
        calls["n"] += 1
        if calls["n"] < 2:
            return sp.CompletedProcess(cmd, 1, stdout="", stderr="transient")
        return sp.CompletedProcess(cmd, 0, stdout='{"ok": true}', stderr="")

    monkeypatch.setattr(full_verify.subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert full_verify.gh_json(["graphql"], retries=2) == {"ok": True}
    assert calls["n"] == 2


def test_graphql_query_braces_balanced():
    # Regression (2026-11-22): the query shipped with 6 '{' and 5 '}',
    # so GitHub rejected every call with "Expected NAME, actual: (none)
    # at [1, 160]" — the failures on Nov 21-22 were a deterministic
    # syntax error in our own query, not a transient GitHub problem.
    from verify.full_verify import GRAPHQL

    assert GRAPHQL.count("{") == GRAPHQL.count("}")
    assert GRAPHQL.rstrip().endswith("}")
