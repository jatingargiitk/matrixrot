"""Load workflow YAML keeping every scalar as text, with its line and quoting style.

GitHub's YAML parser turns an unquoted ``3.10`` into the number ``3.1``.
To spot that, we compose the node tree ourselves instead of letting PyYAML
convert scalars, and remember whether each scalar was written plain.
"""

from __future__ import annotations

import yaml


class S(str):
    """A YAML scalar as written, plus where it came from."""

    line: int
    plain: bool

    def __new__(cls, value: str, line: int = 0, plain: bool = False):
        obj = super().__new__(cls, value)
        obj.line = line
        obj.plain = plain
        return obj


class Map(dict):
    line: int = 0


class Seq(list):
    line: int = 0


def _convert(node):
    if isinstance(node, yaml.ScalarNode):
        return S(node.value, node.start_mark.line + 1, node.style is None)
    if isinstance(node, yaml.SequenceNode):
        out = Seq(_convert(n) for n in node.value)
        out.line = node.start_mark.line + 1
        return out
    if isinstance(node, yaml.MappingNode):
        out = Map()
        out.line = node.start_mark.line + 1
        for k, v in node.value:
            key = _convert(k)
            if isinstance(key, S) and key == "<<" and isinstance(v, yaml.MappingNode):
                for mk, mv in _convert(v).items():
                    out.setdefault(mk, mv)
                continue
            out[str(key) if isinstance(key, S) else repr(key)] = _convert(v)
        return out
    raise TypeError(f"unexpected YAML node {node!r}")


def load(text: str):
    """Return the document as Map/Seq/S objects (None for an empty file)."""
    node = yaml.compose(text, Loader=yaml.SafeLoader)
    if node is None:
        return None
    return _convert(node)


def yaml_number_reading(s: str) -> str | None:
    """If a plain scalar would be read as a float that prints differently, return that text."""
    import re

    if re.fullmatch(r"[0-9]+\.[0-9]+", s):
        as_float = repr(float(s))
        if as_float != s:
            return as_float
    return None
