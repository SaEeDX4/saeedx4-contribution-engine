

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
