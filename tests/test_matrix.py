import pytest

from matrixrot import matrix as mx
from matrixrot.yamlsrc import load


def m(text):
    return load(text)["matrix"]


def test_product():
    combos = mx.expand(m("matrix:\n  os: [a, b]\n  py: ['1', '2']\n"))
    assert [(c["os"], c["py"]) for c in combos] == [("a", "1"), ("a", "2"), ("b", "1"), ("b", "2")]


def test_exclude_partial_match():
    combos = mx.expand(m("matrix:\n  os: [a, b]\n  py: ['1', '2']\n  exclude:\n    - os: b\n"))
    assert [(c["os"], c["py"]) for c in combos] == [("a", "1"), ("a", "2")]


def test_include_extends_matching_and_adds_new():
    combos = mx.expand(m(
        "matrix:\n  os: [a, b]\n  include:\n    - os: a\n      extra: x\n    - os: c\n      py: '9'\n"))
    assert combos[0] == {"os": "a", "extra": "x"}
    assert combos[1] == {"os": "b"}
    assert combos[2] == {"os": "c", "py": "9"}


def test_include_only_matrix():
    combos = mx.expand(m("matrix:\n  include:\n    - py: '3.12'\n    - py: '3.13'\n"))
    assert [c["py"] for c in combos] == ["3.12", "3.13"]


def test_no_matrix():
    assert mx.expand(None) == [{}]


def test_expression_matrix_is_unresolved():
    with pytest.raises(mx.Unresolved):
        mx.expand(m("matrix: ${{ fromJSON(needs.a.outputs.m) }}\n"))


def test_substitute_whole_keeps_source_scalar():
    doc = load("matrix:\n  py: [3.10]\n")
    combo = mx.expand(doc["matrix"])[0]
    got = mx.substitute("${{ matrix.py }}", combo)
    assert got == "3.10" and got.plain and got.line == 2


def test_substitute_inside_string_and_nested():
    combo = {"cfg": {"os": "ubuntu-24.04"}}
    assert mx.substitute("${{ matrix.cfg.os }}", combo) == "ubuntu-24.04"
    assert mx.substitute("x-${{ matrix.cfg.os }}", combo) == "x-ubuntu-24.04"


def test_substitute_other_expression_unresolved():
    with pytest.raises(mx.Unresolved):
        mx.substitute("${{ inputs.py }}", {})


def test_missing_matrix_key_unresolved():
    with pytest.raises(mx.Unresolved):
        mx.substitute("${{ matrix.nope }}", {"py": "3"})
