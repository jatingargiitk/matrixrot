from matrixrot.check import ERROR, SKIP, WARN, check_text, parse_spec


def wf(runs_on, version, matrix="", extra_with=""):
    return f"""
on: push
jobs:
  test:
    runs-on: {runs_on}
{matrix}
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: {version}
{extra_with}
"""


def levels(fs):
    return [f.level for f in fs]


def test_parse_spec_forms():
    assert parse_spec("3.12").prefix == ("3", "12")
    assert parse_spec("3.x").prefix == ("3",)
    s = parse_spec("3.13t")
    assert s.freethreaded and s.prefix == ("3", "13")
    assert parse_spec("3.15-dev").prerelease
    assert parse_spec("pypy3.10") is None
    assert parse_spec(">=3.9") is None


def test_available_is_clean(data):
    assert check_text(wf("ubuntu-24.04", "'3.9'"), "w.yml", data) == []


def test_missing_on_pinned_image_is_error(data):
    fs = check_text(wf("ubuntu-26.04", "'3.9'"), "w.yml", data)
    assert levels(fs) == [ERROR]
    assert "no build for ubuntu-26.04" in fs[0].message
    assert "ubuntu-24.04" in fs[0].hint
    assert "ubuntu-26.04 has 3.10 to 3.13" in fs[0].hint


def test_latest_drift_warning(data):
    fs = check_text(wf("ubuntu-latest", "'3.9'"), "w.yml", data)
    assert levels(fs) == [WARN]
    assert "Ubuntu 26.04" in fs[0].message
    assert fs[0].hint.startswith("pin runs-on to ubuntu-24.04")


def test_latest_no_warning_when_newest_has_it(data):
    assert check_text(wf("ubuntu-latest", "'3.13'"), "w.yml", data) == []


def test_unquoted_float(data):
    fs = check_text(wf("ubuntu-24.04", "3.10"), "w.yml", data)
    assert levels(fs) == [ERROR]
    assert "reads it as 3.1" in fs[0].message


def test_unquoted_float_inside_matrix_reported_once(data):
    m = "    strategy:\n      matrix:\n        os: [ubuntu-24.04, ubuntu-22.04]\n        py: ['3.9', 3.10]"
    fs = check_text(wf("${{ matrix.os }}", "${{ matrix.py }}", m), "w.yml", data)
    assert levels(fs) == [ERROR]
    assert fs[0].line == 9


def test_unquoted_without_trailing_zero_is_fine(data):
    assert check_text(wf("ubuntu-24.04", "3.9"), "w.yml", data) == []


def test_matrix_runs_on_and_arch(data):
    m = "    strategy:\n      matrix:\n        os: [macos-latest, macos-15-intel]\n        py: ['3.8']"
    fs = check_text(wf("${{ matrix.os }}", "${{ matrix.py }}", m), "w.yml", data)
    assert levels(fs) == [ERROR]
    assert "macos-latest" in fs[0].message and "arm64" in fs[0].message
    assert "macos-15-intel" in fs[0].hint


def test_architecture_input(data):
    fs = check_text(wf("windows-latest", "'3.9'", extra_with="          architecture: x86"), "w.yml", data)
    assert levels(fs) == [ERROR] and "x86" in fs[0].message
    assert check_text(wf("windows-latest", "'3.10'", extra_with="          architecture: x86"), "w.yml", data) == []


def test_freethreaded(data):
    assert check_text(wf("ubuntu-24.04", "'3.13t'"), "w.yml", data) == []
    assert levels(check_text(wf("ubuntu-26.04", "'3.13t'"), "w.yml", data)) == [ERROR]


def test_prereleases(data):
    assert levels(check_text(wf("ubuntu-24.04", "'3.15'"), "w.yml", data)) == [ERROR]
    assert check_text(wf("ubuntu-24.04", "'3.15'", extra_with="          allow-prereleases: true"), "w.yml", data) == []
    assert check_text(wf("ubuntu-24.04", "'3.15-dev'"), "w.yml", data) == []


def test_multiline_versions(data):
    fs = check_text(wf("ubuntu-26.04", "|\n            3.10\n            3.9"), "w.yml", data)
    assert levels(fs) == [ERROR] and "3.9" in fs[0].message


def test_skips(data):
    assert levels(check_text(wf("[self-hosted, linux]", "'3.9'"), "w.yml", data)) == [SKIP]
    assert levels(check_text(wf("my-runner", "'3.9'"), "w.yml", data)) == [SKIP]
    assert levels(check_text(wf("ubuntu-24.04", "${{ inputs.py }}"), "w.yml", data)) == [SKIP]
    assert levels(check_text(wf("ubuntu-24.04", "pypy3.10"), "w.yml", data)) == [SKIP]


def test_container_job_skipped(data):
    text = wf("ubuntu-24.04", "'3.9'").replace("    runs-on:", "    container: python:3.9\n    runs-on:")
    assert levels(check_text(text, "w.yml", data)) == [SKIP]


def test_jobs_without_setup_python_ignored(data):
    text = "on: push\njobs:\n  a:\n    runs-on: ubuntu-26.04\n    steps:\n      - run: echo hi\n"
    assert check_text(text, "w.yml", data) == []


def test_bad_yaml(data):
    fs = check_text("jobs: [\n", "w.yml", data)
    assert levels(fs) == [ERROR] and "could not parse" in fs[0].message


def test_exclude_removes_failing_combo(data):
    m = ("    strategy:\n      matrix:\n        os: [ubuntu-24.04, ubuntu-26.04]\n        py: ['3.9']\n"
         "        exclude:\n          - os: ubuntu-26.04\n            py: '3.9'")
    assert check_text(wf("${{ matrix.os }}", "${{ matrix.py }}", m), "w.yml", data) == []
