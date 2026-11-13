import json

from matrixrot import cli, sources

README = """
| Image | Architecture | YAML Label | Included Software |
| --------------------| ---------------------|---------------------|---------------------|
| Ubuntu 26.04<br>![Endpoint Badge](https://x) | x64 | `ubuntu-26.04` | [ubuntu-26.04] |
| Ubuntu 24.04<br>![Endpoint Badge](https://x) | x64 | `ubuntu-latest` or `ubuntu-24.04` | [ubuntu-24.04] |
| Ubuntu 24.04 Arm64<br>![Endpoint Badge](https://x) | arm64 | `ubuntu-24.04-arm` | [x] |
| macOS 26 Arm64<br>![Endpoint Badge](https://x) | arm64 | `macos-latest`, `macos-26` or `macos-26-xlarge` | [x] |
| Windows Server 2025<br>![Endpoint Badge](https://x) | x64 | `windows-latest`, `windows-2025` | [x] |
"""


def test_parse_runner_readme():
    labels = sources.parse_runner_readme(README)
    assert labels["ubuntu-latest"] == {"os": "linux", "version": "24.04", "arch": "x64", "image": "Ubuntu 24.04"}
    assert labels["ubuntu-24.04-arm"]["arch"] == "arm64"
    assert labels["macos-26-xlarge"]["os"] == "darwin" and labels["macos-26-xlarge"]["version"] is None
    assert labels["windows-2025"]["os"] == "win32"
    assert sources.newest_linux_version(labels, "x64") == "26.04"


def test_compact_manifest():
    raw = [{"version": "3.9.25", "stable": True, "files": [
        {"platform": "linux", "platform_version": "24.04", "arch": "x64"},
        {"platform": "darwin", "arch": "arm64"}]}]
    assert sources.compact_python_manifest(raw) == {
        "3.9.25": {"stable": True, "files": ["darwin//arm64", "linux/24.04/x64"]}}


def test_bundled_snapshot_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    py = sources.load_python_versions()
    rn = sources.load_runners()
    assert len(py["versions"]) > 50
    assert "ubuntu-latest" in rn["labels"]


def _write(tmp_path, body):
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True)
    (d / "ci.yml").write_text(body)
    return d


def test_cli_exit_codes_and_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    d = _write(tmp_path, "jobs:\n  t:\n    runs-on: ubuntu-24.04\n    steps:\n"
                         "      - uses: actions/setup-python@v5\n        with:\n          python-version: 3.10\n")
    assert cli.main([str(d)]) == 1
    out = capsys.readouterr().out
    assert "reads it as 3.1" in out and "1 error(s)" in out
    assert cli.main([str(d), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["findings"][0]["level"] == "error"


def test_cli_missing_path(tmp_path, capsys):
    assert cli.main([str(tmp_path / "nope")]) == 2


def test_cli_refresh_failure_falls_back(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def boom():
        raise OSError("offline")

    monkeypatch.setattr(sources, "refresh", boom)
    d = _write(tmp_path, "jobs: {}\n")
    assert cli.main([str(d), "--refresh"]) == 0
    assert "refresh failed (offline)" in capsys.readouterr().err


def test_cli_data_info(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert cli.main(["--data-info"]) == 0
    assert "python manifest:" in capsys.readouterr().out
