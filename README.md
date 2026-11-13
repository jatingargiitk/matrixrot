# matrixrot

[![ci](https://github.com/jatingargiitk/matrixrot/actions/workflows/ci.yml/badge.svg)](https://github.com/jatingargiitk/matrixrot/actions/workflows/ci.yml)

Find the `actions/setup-python` versions in your GitHub Actions workflows that can't install on the runner they target, before a push finds them for you.

Python builds for hosted runners come from [actions/python-versions](https://github.com/actions/python-versions), and each build exists only for certain OS images and CPU architectures. When a runner image moves on, old versions quietly stop existing for it. This is the failure that prompted the tool, from a real run where `ubuntu-latest` had moved to Ubuntu 26.04:

```
Version 3.9 was not found in the local cache
##[error]The version '3.9' with architecture 'x64' was not found for Ubuntu 26.04.
```

matrixrot expands every job's `strategy.matrix` (including `include` and `exclude`), resolves `runs-on` and `python-version` for each combination, and checks the pair against the Python manifest and the runner-images label table. It doesn't run anything.

## What it catches

- **A version with no build for the image.** For example `3.9` on `ubuntu-26.04`, or `3.8` on arm64 macOS if the manifest has no arm64 build for it. The fix line says which labels do have it and which versions the runner has.
- **A version that only works until `-latest` moves.** `ubuntu-latest` is listed as Ubuntu 24.04 in the runner-images README, but `-latest` labels migrate gradually, so some runs already land on the newest image. This is a warning (use `--strict` to fail on it).
- **Unquoted versions YAML turns into numbers.** `python-version: 3.10` is read as `3.1`.
- It understands `architecture` (for example x86 on Windows), `allow-prereleases`, `-dev` versions, free-threaded `3.13t` builds, and multi-line `python-version` lists.

## Install

```
pip install git+https://github.com/jatingargiitk/matrixrot
```

It needs Python 3.9+ and PyYAML.

## Usage

Run it from a repository root (it reads `.github/workflows` by default), or pass files and directories:

```
matrixrot
matrixrot .github/workflows/ci.yml
matrixrot --refresh          # fetch the latest manifest and runner labels first
matrixrot --json             # machine-readable findings
matrixrot --strict           # also fail on warnings
matrixrot --show-skipped     # list what couldn't be checked and why
```

Exit codes: `0` clean, `1` errors (or warnings with `--strict`), `2` a path doesn't exist.

## Example

[`examples/.github/workflows/ci.yml`](examples/.github/workflows/ci.yml) has a 3x4 matrix plus a lint job. Running `matrixrot` in `examples/` prints:

```
.github/workflows/ci.yml:9  ERROR  job test
    python-version 3.10 is unquoted, so YAML reads it as 3.1
    fix: write it as '3.10'
.github/workflows/ci.yml:27  ERROR  job lint
    Python 3.9 (x64) has no build for ubuntu-26.04 (Ubuntu 26.04)
    fix: available on ubuntu-22.04, ubuntu-22.04-arm, ubuntu-24.04, ubuntu-24.04-arm ...; ubuntu-26.04 has 3.10 to 3.15
.github/workflows/ci.yml:9  WARN   job test [os=ubuntu-latest, python=3.8]
    Python 3.8 is on ubuntu-latest today (Ubuntu 24.04), but has no build for Ubuntu 26.04, the newest image; -latest labels move there gradually, so some runs already land on it
    fix: pin runs-on to ubuntu-24.04 or drop 3.8
.github/workflows/ci.yml:9  WARN   job test [os=ubuntu-latest, python=3.9]
    Python 3.9 is on ubuntu-latest today (Ubuntu 24.04), but has no build for Ubuntu 26.04, the newest image; -latest labels move there gradually, so some runs already land on it
    fix: pin runs-on to ubuntu-24.04 or drop 3.9
2 error(s), 2 warning(s)  [data: python manifest 2026-11-13, runners 2026-11-13]
```

The exit code is `1`. The `python=3.10` combinations aren't checked further because the version itself is wrong.

## As a GitHub Action

```yaml
- uses: actions/checkout@v4
- uses: jatingargiitk/matrixrot@main
  with:
    strict: "true"     # optional: fail on -latest warnings too
    # paths: .github/workflows
    # refresh: "true"  # default: fetch live data first
```

This repo's own CI runs it on itself.

## Data

Two snapshots ship in the package (dates are printed in every summary and by `matrixrot --data-info`):

- `versions-manifest.json` from [actions/python-versions](https://github.com/actions/python-versions), compacted to version, stable flag and platform/OS version/arch.
- The image table in the [actions/runner-images README](https://github.com/actions/runner-images), parsed into label to OS, OS version and arch.

`--refresh` fetches both into `~/.cache/matrixrot` (or `$XDG_CACHE_HOME/matrixrot`), and later runs use that cache ahead of the bundled snapshot. If the fetch fails, it says so and keeps using what it has. `python scripts/snapshot.py` regenerates the bundled copy.

## Limits

- Only GitHub-hosted runner labels are checked. Self-hosted runners, runner groups, unknown labels and jobs with a `container` are skipped.
- Only `${{ matrix.* }}` expressions are resolved. A matrix built with `fromJSON(...)`, or a version from `inputs`, `env` or `vars`, is skipped. So is `python-version-file`.
- PyPy, GraalPy and range specs like `>=3.9` are skipped.
- It checks availability in the manifest, which is what `setup-python` downloads from. It can't tell you whether your tests pass on that version.

## License

MIT
