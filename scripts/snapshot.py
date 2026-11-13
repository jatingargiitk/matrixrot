"""Regenerate the bundled data snapshot: python scripts/snapshot.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from matrixrot import sources  # noqa: E402

py, runners = sources.write_snapshots(sources.DATA_DIR)
print(f"{len(py['versions'])} python releases, {len(runners['labels'])} runner labels")
