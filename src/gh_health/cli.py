"""Command line entry point: read workflow-runs JSON, print a health report."""

from __future__ import annotations

import argparse
import json
import sys

from .report import render_markdown, summarize_runs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gh-health")
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Path to a workflow-runs JSON file (default: stdin).",
    )
    args = parser.parse_args(argv)
    raw = sys.stdin.read() if args.input == "-" else open(args.input, encoding="utf-8").read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON input: {exc}", file=sys.stderr)
        return 2
    runs = data.get("workflow_runs", []) if isinstance(data, dict) else []
    sys.stdout.write(render_markdown(summarize_runs(runs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
