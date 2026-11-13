"""Load and refresh the two upstream facts matrixrot checks against.

* actions/python-versions ``versions-manifest.json``: which Python builds
  exist for which platform, OS version and architecture.
* actions/runner-images ``README.md``: which ``runs-on`` label maps to which
  image (OS, OS version, architecture).

A snapshot of both ships inside the package so checks work offline;
``refresh()`` rebuilds them from GitHub.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import urllib.request
from pathlib import Path

PYTHON_MANIFEST_URL = (
    "https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json"
)
RUNNER_README_URL = "https://raw.githubusercontent.com/actions/runner-images/main/README.md"

DATA_DIR = Path(__file__).parent / "data"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return Path(base) / "matrixrot"


def _fetch(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "matrixrot"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https URLs)
        return resp.read().decode("utf-8")


def compact_python_manifest(raw: list) -> dict:
    """Shrink the upstream manifest to version -> stable flag + 'platform/osver/arch' keys."""
    versions = {}
    for rel in raw:
        files = sorted(
            {
                "{}/{}/{}".format(f.get("platform", ""), f.get("platform_version") or "", f.get("arch", ""))
                for f in rel.get("files", [])
            }
        )
        versions[rel["version"]] = {"stable": bool(rel.get("stable")), "files": files}
    return versions


_OS_PATTERNS = [
    (re.compile(r"^Ubuntu (\d+\.\d+)"), "linux"),
    (re.compile(r"^macOS (\d+)"), "darwin"),
    (re.compile(r"^Windows"), "win32"),
]


def parse_runner_readme(text: str) -> dict:
    """Parse the 'Available Images' table into label -> {os, version, arch, image}.

    Rows look like ``| Ubuntu 24.04<br>![badge](...) | x64 | `ubuntu-latest` or `ubuntu-24.04` | [ubuntu-24.04] |``.
    """
    labels = {}
    for line in text.splitlines():
        if not line.startswith("|") or "`" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        image = re.sub(r"<br>.*$", "", cells[0]).strip()
        image = re.sub(r"\[!\[.*$", "", image).strip()
        arch = cells[1].strip()
        if arch not in ("x64", "arm64"):
            continue
        os_name, os_version = None, None
        for pat, name in _OS_PATTERNS:
            m = pat.match(image)
            if m:
                os_name = name
                os_version = m.group(1) if m.groups() else None
                break
        if os_name is None:
            continue
        if os_name == "linux" and os_version is None:
            continue
        for label in re.findall(r"`([^`]+)`", cells[2]):
            labels[label] = {"os": os_name, "version": os_version if os_name == "linux" else None,
                             "arch": arch, "image": image}
    return labels


def newest_linux_version(labels: dict, arch: str) -> str | None:
    vers = {v["version"] for v in labels.values() if v["os"] == "linux" and v["arch"] == arch and v["version"]}
    if not vers:
        return None
    return max(vers, key=lambda s: tuple(int(p) for p in s.split(".")))


def _read(name: str) -> dict:
    cached = cache_dir() / name
    path = cached if cached.exists() else DATA_DIR / name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_python_versions() -> dict:
    return _read("python-versions.json")


def load_runners() -> dict:
    return _read("runners.json")


def build_snapshots() -> tuple[dict, dict]:
    today = _dt.date.today().isoformat()
    py = {"source": PYTHON_MANIFEST_URL, "fetched": today,
          "versions": compact_python_manifest(json.loads(_fetch(PYTHON_MANIFEST_URL)))}
    labels = parse_runner_readme(_fetch(RUNNER_README_URL))
    if not labels:
        raise RuntimeError("could not parse any runner labels from " + RUNNER_README_URL)
    runners = {"source": RUNNER_README_URL, "fetched": today, "labels": labels}
    return py, runners


def write_snapshots(target: Path) -> tuple[dict, dict]:
    py, runners = build_snapshots()
    target.mkdir(parents=True, exist_ok=True)
    with open(target / "python-versions.json", "w", encoding="utf-8") as fh:
        json.dump(py, fh, separators=(",", ":"), sort_keys=True)
    with open(target / "runners.json", "w", encoding="utf-8") as fh:
        json.dump(runners, fh, indent=1, sort_keys=True)
    return py, runners


def refresh() -> tuple[dict, dict]:
    """Fetch fresh data into the user cache (used ahead of the bundled snapshot)."""
    return write_snapshots(cache_dir())
