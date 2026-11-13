import pytest

from matrixrot.check import Data


def _files(*keys):
    return sorted(keys)


PY = {
    "fetched": "test",
    "versions": {
        "3.9.25": {"stable": True, "files": _files("linux/22.04/x64", "linux/24.04/x64", "darwin//arm64", "darwin//x64", "win32//x64")},
        "3.10.19": {"stable": True, "files": _files("linux/22.04/x64", "linux/24.04/x64", "linux/26.04/x64", "darwin//arm64", "win32//x64", "win32//x86")},
        "3.8.10": {"stable": True, "files": _files("linux/22.04/x64", "darwin//x64", "win32//x64")},
        "3.13.9": {"stable": True, "files": _files("linux/24.04/x64", "linux/26.04/x64", "linux/24.04/x64-freethreaded", "darwin//arm64", "win32//x64")},
        "3.15.0-alpha.1": {"stable": False, "files": _files("linux/24.04/x64", "linux/26.04/x64")},
    },
}

RUNNERS = {
    "fetched": "test",
    "labels": {
        "ubuntu-latest": {"os": "linux", "version": "24.04", "arch": "x64", "image": "Ubuntu 24.04"},
        "ubuntu-24.04": {"os": "linux", "version": "24.04", "arch": "x64", "image": "Ubuntu 24.04"},
        "ubuntu-22.04": {"os": "linux", "version": "22.04", "arch": "x64", "image": "Ubuntu 22.04"},
        "ubuntu-26.04": {"os": "linux", "version": "26.04", "arch": "x64", "image": "Ubuntu 26.04"},
        "macos-latest": {"os": "darwin", "version": None, "arch": "arm64", "image": "macOS 26 Arm64"},
        "macos-15-intel": {"os": "darwin", "version": None, "arch": "x64", "image": "macOS 15"},
        "windows-latest": {"os": "win32", "version": None, "arch": "x64", "image": "Windows Server 2025"},
    },
}


@pytest.fixture
def data():
    return Data(PY, RUNNERS)
