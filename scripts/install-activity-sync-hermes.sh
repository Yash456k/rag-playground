#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

install -d -m 700 "$unit_dir"
install -m 600 "$repo_root/deploy/systemd/portfolio-activity-sync.service" "$unit_dir/portfolio-activity-sync.service"
install -m 600 "$repo_root/deploy/systemd/portfolio-activity-sync.timer" "$unit_dir/portfolio-activity-sync.timer"

systemctl --user daemon-reload
systemctl --user enable --now portfolio-activity-sync.timer
systemctl --user status portfolio-activity-sync.timer --no-pager
