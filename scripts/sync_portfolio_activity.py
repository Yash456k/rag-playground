#!/usr/bin/env python3
"""Refresh the portfolio activity heatmaps from Codex and GitHub.

Codex data comes from the authenticated profile statistics used by the desktop
app. GitHub data is read from the authenticated `gh` CLI. With --publish, the
refreshed snapshot is committed and pushed so the portfolio redeploys.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "frontend" / "src" / "data" / "activity.json"
BOT_NAME = "Portfolio Activity Bot"
BOT_EMAIL = "portfolio-activity-bot@users.noreply.github.com"
CODEX_PROFILE_URL = "https://chatgpt.com/backend-api/wham/profiles/me"


def find_codex_home() -> Path:
    candidates: list[Path] = []
    if configured := os.environ.get("CODEX_HOME"):
        candidates.append(Path(configured).expanduser())
    candidates.append(Path.home() / ".codex")
    candidates.extend(Path("/mnt/c/Users").glob("*/.codex"))

    available = [candidate for candidate in candidates if (candidate / "sessions").exists()]
    if available:
        return max(
            available,
            key=lambda candidate: sum(1 for _ in (candidate / "sessions").rglob("*.jsonl")),
        )
    raise RuntimeError("Could not find a Codex home containing session logs")


def read_codex_activity(codex_home: Path, start: date, end: date) -> dict[str, Any]:
    auth_path = codex_home / "auth.json"
    if not auth_path.exists():
        raise RuntimeError(f"Codex authentication was not found at {auth_path}")

    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Codex authentication could not be read") from error

    tokens = auth.get("tokens") or {}
    access_token = tokens.get("access_token")
    account_id = tokens.get("account_id")
    if not access_token or not account_id:
        raise RuntimeError("Codex authentication is missing an access token or account ID")

    request = Request(
        CODEX_PROFILE_URL,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "ChatGPT-Account-ID": account_id,
            "OAI-Language": "en",
            "Originator": "Codex Desktop",
            "User-Agent": "Portfolio Activity Sync/1.0",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            profile = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"Codex profile request failed with HTTP {error.code}") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("Codex profile request failed") from error

    stats = profile.get("stats") or {}
    buckets = stats.get("daily_usage_buckets")
    if not isinstance(buckets, list):
        raise RuntimeError("Codex profile response did not include daily usage")

    days = sorted(
        (
            {"date": str(bucket.get("start_date", ""))[:10], "tokens": int(bucket.get("tokens", 0))}
            for bucket in buckets
            if start.isoformat() <= str(bucket.get("start_date", ""))[:10] <= end.isoformat()
            and int(bucket.get("tokens", 0)) > 0
        ),
        key=lambda item: item["date"],
    )
    peak = max(days, key=lambda item: item["tokens"], default=None)
    return {
        "total": sum(item["tokens"] for item in days),
        "lifetimeTotal": int(stats.get("lifetime_tokens", 0)),
        "peakDailyTokens": int(stats.get("peak_daily_tokens", 0)),
        "activeDays": len(days),
        "peak": {"date": peak["date"], "count": peak["tokens"]} if peak else None,
        "days": days,
    }


def run_gh_graphql(start: date, end: date) -> dict[str, Any]:
    query = """
    query($from: DateTime!, $to: DateTime!) {
      viewer {
        login
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    command = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={query}",
        "-F",
        f"from={start.isoformat()}T00:00:00Z",
        "-F",
        f"to={end.isoformat()}T23:59:59Z",
    ]
    result = subprocess.run(command, cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    return json.loads(result.stdout)["data"]["viewer"]


def read_github_activity(start: date, end: date) -> dict[str, Any]:
    viewer = run_gh_graphql(start, end)
    calendar = viewer["contributionsCollection"]["contributionCalendar"]
    days = [
        {"date": item["date"], "count": item["contributionCount"]}
        for week in calendar["weeks"]
        for item in week["contributionDays"]
        if start.isoformat() <= item["date"] <= end.isoformat()
        and item["contributionCount"] > 0
    ]
    peak = max(days, key=lambda item: item["count"], default=None)
    return {
        "username": viewer["login"],
        "total": sum(item["count"] for item in days),
        "activeDays": len(days),
        "peak": peak,
        "days": days,
    }


def write_snapshot(snapshot: dict[str, Any]) -> bool:
    rendered = json.dumps(snapshot, indent=2, ensure_ascii=True) + "\n"
    previous = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
    if previous == rendered:
        return False
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    return True


def publish_snapshot() -> None:
    relative_output = OUTPUT_PATH.relative_to(REPO_ROOT)
    subprocess.run(["git", "add", str(relative_output)], cwd=REPO_ROOT, check=True)
    changed = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=REPO_ROOT, check=False
    ).returncode != 0
    if not changed:
        print("Activity snapshot is already current; nothing to publish.")
        return

    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": BOT_NAME,
            "GIT_AUTHOR_EMAIL": BOT_EMAIL,
            "GIT_COMMITTER_NAME": BOT_NAME,
            "GIT_COMMITTER_EMAIL": BOT_EMAIL,
        }
    )
    subprocess.run(
        ["git", "commit", "-m", "chore: refresh portfolio activity"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )
    subprocess.run(["git", "push"], cwd=REPO_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="commit and push the refreshed activity snapshot when it changed",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    end = datetime.now().astimezone().date()
    start = end - timedelta(days=365)
    codex_home = find_codex_home()

    snapshot = {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "codex": read_codex_activity(codex_home, start, end),
        "github": read_github_activity(start, end),
    }
    changed = write_snapshot(snapshot)
    print(
        f"Refreshed {OUTPUT_PATH}: "
        f"{snapshot['codex']['total']:,} Codex tokens, "
        f"{snapshot['github']['total']:,} GitHub contributions"
    )
    if args.publish and changed:
        publish_snapshot()


if __name__ == "__main__":
    main()
