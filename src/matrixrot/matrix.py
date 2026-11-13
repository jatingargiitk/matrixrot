"""Expand a job's ``strategy.matrix`` the way GitHub Actions does."""

from __future__ import annotations

import itertools
import re

from .yamlsrc import Map, S, Seq

EXPR = re.compile(r"\$\{\{\s*(.*?)\s*\}\}")
MATRIX_REF = re.compile(r"^matrix((?:\.[A-Za-z0-9_-]+)+)$")


class Unresolved(Exception):
    """A value depends on an expression we can't evaluate statically."""


def _same(a, b) -> bool:
    return _plain(a) == _plain(b)


def _plain(v):
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return str(v)


def expand(matrix) -> list[dict]:
    """Return the list of combinations (each a dict). An empty matrix gives ``[{}]``.

    Raises Unresolved when the matrix itself is an expression (e.g. ``fromJSON``).
    """
    if matrix is None:
        return [{}]
    if isinstance(matrix, S):
        raise Unresolved(f"matrix is an expression: {matrix}")
    if not isinstance(matrix, Map):
        raise Unresolved("matrix is not a mapping")

    keys = [k for k in matrix if k not in ("include", "exclude")]
    axes = []
    for k in keys:
        v = matrix[k]
        if isinstance(v, S):
            raise Unresolved(f"matrix.{k} is an expression: {v}")
        if not isinstance(v, Seq):
            raise Unresolved(f"matrix.{k} is not a list")
        axes.append(list(v))

    combos = [dict(zip(keys, vals)) for vals in itertools.product(*axes)] if keys else []

    excludes = matrix.get("exclude") or []
    if isinstance(excludes, S):
        raise Unresolved(f"matrix.exclude is an expression: {excludes}")
    for ex in excludes:
        if isinstance(ex, Map):
            combos = [c for c in combos if not all(k in c and _same(c[k], v) for k, v in ex.items())]

    includes = matrix.get("include") or []
    if isinstance(includes, S):
        raise Unresolved(f"matrix.include is an expression: {includes}")
    original = set(keys)
    extra = []
    for inc in includes:
        if not isinstance(inc, Map):
            continue
        matched = False
        for c in combos:
            if all(k not in original or _same(c.get(k), v) for k, v in inc.items()):
                matched = True
                for k, v in inc.items():
                    if k not in original:
                        c[k] = v
        if not matched:
            extra.append(dict(inc))
    combos.extend(extra)
    return combos or [{}]


def lookup(combo: dict, path: str):
    cur = combo
    for part in path.strip(".").split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise Unresolved(f"matrix.{path.strip('.')} is not set in this combination")
    return cur


def substitute(value, combo: dict):
    """Resolve ``${{ matrix.x }}`` references in a scalar.

    If the whole scalar is one matrix reference, the matrix value itself is
    returned (so its line and quoting survive). Any other expression raises
    Unresolved.
    """
    if not isinstance(value, str):
        return value
    whole = EXPR.fullmatch(value.strip())
    if whole:
        m = MATRIX_REF.match(whole.group(1))
        if not m:
            raise Unresolved(f"expression {value.strip()} can't be evaluated statically")
        return lookup(combo, m.group(1))

    def repl(m):
        ref = MATRIX_REF.match(m.group(1))
        if not ref:
            raise Unresolved(f"expression {m.group(0)} can't be evaluated statically")
        got = lookup(combo, ref.group(1))
        if isinstance(got, (dict, list)):
            raise Unresolved(f"{m.group(0)} is not a scalar")
        return str(got)

    if "${{" not in value:
        return value
    line = getattr(value, "line", 0)
    return S(EXPR.sub(repl, value), line, False)


def describe(combo: dict) -> str:
    parts = []
    for k, v in combo.items():
        if isinstance(v, (dict, list)):
            v = _plain(v)
        parts.append(f"{k}={v}")
    return ", ".join(parts)
