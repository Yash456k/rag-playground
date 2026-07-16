from __future__ import annotations

import json
import stat
from pathlib import Path

from scripts.sync_portfolio_activity import write_snapshot


def test_write_snapshot_is_atomic_and_publicly_readable(tmp_path: Path) -> None:
    output = tmp_path / "activity" / "activity.json"
    snapshot = {"generatedAt": "2026-07-16T05:55:09Z", "safe": True}

    changed = write_snapshot(snapshot, output)

    assert changed is True
    assert json.loads(output.read_text(encoding="utf-8")) == snapshot
    assert stat.S_IMODE(output.stat().st_mode) == 0o644
    assert stat.S_IMODE(output.parent.stat().st_mode) == 0o755
    assert list(output.parent.glob(f".{output.name}.*")) == []
    assert write_snapshot(snapshot, output) is False
