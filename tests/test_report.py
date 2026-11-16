from gh_health.report import render_markdown, summarize_runs


def _run(name, status="completed", conclusion="success"):
    return {"name": name, "status": status, "conclusion": conclusion}


def test_empty():
    assert summarize_runs([]) == []
    assert "no runs" in render_markdown([])


def test_counts_and_rate():
    runs = [
        _run("CI"),
        _run("CI"),
        _run("CI", conclusion="failure"),
        _run("CI", conclusion="cancelled"),
        _run("CI", status="in_progress", conclusion=None),
        _run("Verify", conclusion="failure"),
    ]
    health = {h.name: h for h in summarize_runs(runs)}
    ci = health["CI"]
    assert (ci.total, ci.succeeded, ci.failed, ci.cancelled, ci.in_progress) == (5, 2, 1, 1, 1)
    assert abs(ci.success_rate - 2 / 3) < 1e-9
    assert health["Verify"].success_rate == 0.0


def test_markdown_table():
    md = render_markdown(summarize_runs([_run("CI")]))
    assert "| CI | 1 | 1 | 0 | 0 | 0 | 100% |" in md
