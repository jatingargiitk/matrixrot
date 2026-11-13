"""Check every actions/setup-python step against the runner it will run on."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import matrix as mx
from . import sources
from .yamlsrc import Map, S, Seq, load, yaml_number_reading

ERROR, WARN, SKIP = "error", "warn", "skip"


@dataclass
class Finding:
    level: str
    file: str
    line: int
    job: str
    combo: str
    message: str
    hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Spec:
    raw: str
    prefix: tuple = ()
    freethreaded: bool = False
    prerelease: bool = False


def parse_spec(raw: str) -> Spec | None:
    """Parse a setup-python version. Returns None for forms we don't check (pypy, ranges...)."""
    s = raw.strip()
    low = s.lower()
    if not s or low.startswith(("pypy", "graalpy")):
        return None
    spec = Spec(raw=s)
    if low.endswith("-dev"):
        spec.prerelease = True
        low = low[: -len("-dev")]
    m = re.fullmatch(r"(\d+(?:\.(?:\d+|x)){0,2})(t?)", low)
    if not m:
        return None
    spec.freethreaded = m.group(2) == "t"
    parts = []
    for p in m.group(1).split("."):
        if p == "x":
            break
        parts.append(p)
    spec.prefix = tuple(parts)
    return spec


def _release_parts(version: str) -> tuple:
    return tuple(version.split("-")[0].split("."))


def _minor(version: str) -> str:
    return ".".join(_release_parts(version)[:2])


def _vkey(v: str) -> tuple:
    return tuple(int(p) for p in v.split(".") if p.isdigit())


class Data:
    def __init__(self, python: dict | None = None, runners: dict | None = None):
        self.python = python if python is not None else sources.load_python_versions()
        self.runners = runners if runners is not None else sources.load_runners()
        self.labels = self.runners["labels"]

    def platform_key(self, runner: dict, arch: str, freethreaded: bool) -> str:
        a = arch + ("-freethreaded" if freethreaded else "")
        return "{}/{}/{}".format(runner["os"], runner["version"] or "", a)

    def matches(self, spec: Spec, key: str, allow_pre: bool) -> list[str]:
        out = []
        for ver, rel in self.python["versions"].items():
            if not rel["stable"] and not (allow_pre or spec.prerelease):
                continue
            if _release_parts(ver)[: len(spec.prefix)] != spec.prefix:
                continue
            if key in rel["files"]:
                out.append(ver)
        return out

    def minors_on(self, key: str) -> list[str]:
        mins = {_minor(v) for v, rel in self.python["versions"].items() if rel["stable"] and key in rel["files"]}
        return sorted(mins, key=_vkey)

    def labels_with(self, spec: Spec, arch_of_runner: str, allow_pre: bool, os_name: str) -> list[str]:
        good = []
        for label, r in self.labels.items():
            if r["os"] != os_name:
                continue
            if self.matches(spec, self.platform_key(r, r["arch"], spec.freethreaded), allow_pre):
                good.append(label)
        return sorted(good)


def _runs_on_label(value) -> str | None:
    """Pick the hosted-runner label out of a runs-on value, or None if it's self-hosted/a group."""
    if isinstance(value, S):
        return str(value).strip()
    if isinstance(value, Seq):
        labels = [str(x).strip() for x in value]
        if "self-hosted" in labels:
            return None
        return labels[0] if labels else None
    return None


def _version_lines(value: str) -> list[str]:
    return [ln.strip() for ln in str(value).splitlines() if ln.strip()]


def _truthy(v) -> bool:
    return str(v).strip().lower() == "true"


def check_text(text: str, path: str, data: Data) -> list[Finding]:
    findings: list[Finding] = []
    seen: set = set()

    def add(f: Finding):
        k = (f.level, f.line, f.job, f.combo, f.message)
        if k not in seen:
            seen.add(k)
            findings.append(f)

    try:
        doc = load(text)
    except Exception as exc:  # yaml errors
        return [Finding(ERROR, path, 0, "", "", f"could not parse YAML: {exc}")]
    if not isinstance(doc, Map) or not isinstance(doc.get("jobs"), Map):
        return findings

    for job_id, job in doc["jobs"].items():
        if not isinstance(job, Map) or not isinstance(job.get("steps"), Seq):
            continue
        steps = [s for s in job["steps"] if isinstance(s, Map)
                 and str(s.get("uses", "")).strip().startswith("actions/setup-python@")]
        if not steps:
            continue
        if "container" in job:
            add(Finding(SKIP, path, job.line, job_id, "", "job runs in a container; setup-python there depends on the container image"))
            continue
        strategy = job.get("strategy")
        try:
            combos = mx.expand(strategy.get("matrix") if isinstance(strategy, Map) else None)
        except mx.Unresolved as exc:
            add(Finding(SKIP, path, job.line, job_id, "", str(exc)))
            continue

        for combo in combos:
            cdesc = mx.describe(combo)
            try:
                label = _runs_on_label(mx.substitute(job.get("runs-on"), combo) if isinstance(job.get("runs-on"), S)
                                       else job.get("runs-on"))
            except mx.Unresolved as exc:
                add(Finding(SKIP, path, job.line, job_id, cdesc, f"runs-on: {exc}"))
                continue
            if label is None:
                add(Finding(SKIP, path, job.line, job_id, cdesc, "self-hosted or group runner"))
                continue
            runner = data.labels.get(label)
            if runner is None:
                add(Finding(SKIP, path, job.line, job_id, cdesc, f"runner label '{label}' is not a GitHub-hosted image matrixrot knows"))
                continue

            for step in steps:
                with_ = step.get("with") if isinstance(step.get("with"), Map) else Map()
                if "python-version" not in with_:
                    if "python-version-file" in with_:
                        add(Finding(SKIP, path, step.line, job_id, cdesc, "python-version-file is not read"))
                    continue
                try:
                    pv = mx.substitute(with_["python-version"], combo)
                    arch_v = mx.substitute(with_.get("architecture"), combo) if "architecture" in with_ else None
                    pre_v = mx.substitute(with_.get("allow-prereleases"), combo) if "allow-prereleases" in with_ else None
                except mx.Unresolved as exc:
                    add(Finding(SKIP, path, step.line, job_id, cdesc, str(exc)))
                    continue
                if isinstance(pv, (dict, list)):
                    add(Finding(SKIP, path, step.line, job_id, cdesc, "python-version is not a scalar"))
                    continue
                line = getattr(pv, "line", 0) or step.line
                if isinstance(pv, S) and pv.plain:
                    read_as = yaml_number_reading(pv)
                    if read_as:
                        add(Finding(ERROR, path, line, job_id, "", f"python-version {pv} is unquoted, so YAML reads it as {read_as}",
                                    f"write it as '{pv}'"))
                        continue
                arch = str(arch_v).strip() if arch_v else runner["arch"]
                allow_pre = _truthy(pre_v) if pre_v is not None else False
                for raw in _version_lines(pv):
                    spec = parse_spec(raw)
                    if spec is None:
                        add(Finding(SKIP, path, line, job_id, cdesc, f"version '{raw}' is not checked (pypy, graalpy or a range)"))
                        continue
                    key = data.platform_key(runner, arch, spec.freethreaded)
                    if data.matches(spec, key, allow_pre):
                        if label.endswith("-latest") and runner["os"] == "linux":
                            newest = sources.newest_linux_version(data.labels, runner["arch"])
                            if newest and newest != runner["version"]:
                                nkey = data.platform_key(dict(runner, version=newest), arch, spec.freethreaded)
                                if not data.matches(spec, nkey, allow_pre):
                                    add(Finding(WARN, path, line, job_id, cdesc,
                                                f"Python {raw} is on {label} today ({runner['image']}), but has no build for Ubuntu {newest}, the newest image; -latest labels move there gradually, so some runs already land on it",
                                                f"pin runs-on to ubuntu-{runner['version']}" + ("-arm" if runner["arch"] == "arm64" else "")
                                                + f" or drop {raw}"))
                        continue
                    have = data.minors_on(key)
                    where = data.labels_with(spec, runner["arch"], allow_pre, runner["os"])
                    hint = []
                    if where:
                        hint.append("available on " + ", ".join(where[:4]) + (" ..." if len(where) > 4 else ""))
                    if have:
                        hint.append(f"{label} has {have[0]} to {have[-1]}")
                    add(Finding(ERROR, path, line, job_id, cdesc,
                                f"Python {raw} ({arch}{', free-threaded' if spec.freethreaded else ''}) has no build for {label} ({runner['image']})",
                                "; ".join(hint)))
    return findings


def check_paths(paths, data: Data) -> list[Finding]:
    from pathlib import Path

    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files.extend(sorted(list(p.glob("*.yml")) + list(p.glob("*.yaml"))))
        else:
            files.append(p)
    out = []
    for f in files:
        out.extend(check_text(f.read_text(encoding="utf-8"), str(f), data))
    return out
