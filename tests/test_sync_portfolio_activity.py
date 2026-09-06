from __future__ import annotations

import base64
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import sync_portfolio_activity as sync
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


def fake_auth(tmp_path: Path) -> Path:
    (tmp_path / "auth.json").write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": "old-cli-token",
                    "account_id": "portfolio-account",
                }
            }
        )
    )
    return tmp_path


def managed_token(account: str) -> str:
    claims = {"https://api.openai.com/auth": {"chatgpt_account_id": account}}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"test.{payload}.unsigned"


def test_default_credentials_keep_cli_behavior(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ACTIVITY_CODEX_AUTH_SOURCE", raising=False)
    assert sync.read_codex_credentials(fake_auth(tmp_path)) == (
        "old-cli-token",
        "portfolio-account",
    )


def test_hermes_uses_current_login_without_rewriting_cli_auth(tmp_path: Path, monkeypatch) -> None:
    home = fake_auth(tmp_path)
    original = (home / "auth.json").read_bytes()
    token = managed_token("portfolio-account")
    monkeypatch.setenv("ACTIVITY_CODEX_AUTH_SOURCE", "hermes")
    monkeypatch.setattr(
        sync,
        "import_module",
        lambda _: SimpleNamespace(
            get_codex_auth_status=lambda: {"logged_in": True, "api_key": token},
        ),
    )
    assert sync.read_codex_credentials(home) == (token, "portfolio-account")
    assert (home / "auth.json").read_bytes() == original


@pytest.mark.parametrize(
    "status, message",
    [
        ({"logged_in": False}, "no current Codex login"),
        ({"logged_in": True, "api_key": "malformed"}, "could not be identified"),
        ({"logged_in": True, "api_key": managed_token("other-account")}, "does not match"),
    ],
)
def test_hermes_fails_closed(tmp_path: Path, monkeypatch, status, message: str) -> None:
    monkeypatch.setenv("ACTIVITY_CODEX_AUTH_SOURCE", "hermes")
    monkeypatch.setattr(
        sync,
        "import_module",
        lambda _: SimpleNamespace(
            get_codex_auth_status=lambda: status,
        ),
    )
    with pytest.raises(RuntimeError, match=message):
        sync.read_codex_credentials(fake_auth(tmp_path))


def test_hermes_error_does_not_expose_provider_details(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ACTIVITY_CODEX_AUTH_SOURCE", "hermes")

    def unavailable(_):
        raise RuntimeError("private provider details")

    monkeypatch.setattr(sync, "import_module", unavailable)
    with pytest.raises(RuntimeError, match="could not be resolved") as error:
        sync.read_codex_credentials(fake_auth(tmp_path))
    assert "private provider details" not in str(error.value)
    assert error.value.__suppress_context__
