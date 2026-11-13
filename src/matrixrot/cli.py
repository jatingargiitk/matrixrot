"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__, sources
from .check import ERROR, SKIP, WARN, Data, check_paths


def _fmt(f) -> str:
    where = f"{f.file}:{f.line}" if f.line else f.file
    head = f"{where}  {f.level.upper():5}  job {f.job}" + (f" [{f.combo}]" if f.combo else "")
    lines = [head, f"    {f.message}"]
    if f.hint:
        lines.append(f"    fix: {f.hint}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="matrixrot",
        description="Find setup-python versions in GitHub Actions workflows that can't install on the runner they target.",
    )
    ap.add_argument("paths", nargs="*", help="workflow files or directories (default: .github/workflows)")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    ap.add_argument("--show-skipped", action="store_true", help="list what could not be checked and why")
    ap.add_argument("--refresh", action="store_true", help="fetch the latest Python manifest and runner labels from GitHub first")
    ap.add_argument("--data-info", action="store_true", help="show which data snapshot is in use and exit")
    ap.add_argument("--version", action="version", version=f"matrixrot {__version__}")
    args = ap.parse_args(argv)

    if args.refresh:
        try:
            sources.refresh()
        except Exception as exc:
            print(f"matrixrot: refresh failed ({exc}); using the existing snapshot", file=sys.stderr)

    data = Data()
    if args.data_info:
        print(f"python manifest: {len(data.python['versions'])} releases, fetched {data.python['fetched']}")
        print(f"runner labels:   {len(data.labels)} labels, fetched {data.runners['fetched']}")
        return 0

    paths = args.paths or [os.path.join(".github", "workflows")]
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        print(f"matrixrot: no such file or directory: {', '.join(missing)}", file=sys.stderr)
        return 2

    findings = check_paths(paths, data)
    errors = [f for f in findings if f.level == ERROR]
    warns = [f for f in findings if f.level == WARN]
    skips = [f for f in findings if f.level == SKIP]

    if args.json:
        print(json.dumps({"python_manifest_fetched": data.python["fetched"],
                          "runners_fetched": data.runners["fetched"],
                          "findings": [f.to_dict() for f in findings]}, indent=2))
    else:
        shown = errors + warns + (skips if args.show_skipped else [])
        for f in shown:
            print(_fmt(f))
        summary = f"{len(errors)} error(s), {len(warns)} warning(s)"
        if skips:
            summary += f", {len(skips)} skipped" + ("" if args.show_skipped else " (--show-skipped to list)")
        summary += f"  [data: python manifest {data.python['fetched']}, runners {data.runners['fetched']}]"
        print(summary)

    if errors or (args.strict and warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
