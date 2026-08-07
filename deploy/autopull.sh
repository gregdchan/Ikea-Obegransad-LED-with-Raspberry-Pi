#!/bin/bash
# Pull new commits from GitHub and restart the display only if something changed.
# ponytail: 1-minute cron poll instead of a webhook — the Pi has no inbound access
# from the internet, so polling avoids a tunnel, a runner daemon and stored secrets.
# Upgrade path if 60s of latency ever matters: Tailscale + a GitHub Actions job that
# ssh's in, or a self-hosted runner on the Pi.
set -euo pipefail

cd "$(dirname "$(readlink -f "$0")")/.."

before=$(git rev-parse HEAD)

# --ff-only, not reset --hard: if you've hand-edited files on the Pi, this stops
# and leaves them alone rather than silently deleting your work. To make the Pi a
# throwaway mirror instead, swap these two lines for:
#   git fetch -q origin main && git reset --hard -q origin/main
git fetch -q origin main
git merge --ff-only -q origin/main

after=$(git rev-parse HEAD)

if [ "$before" != "$after" ]; then
  echo "deploy: $before -> $after, restarting"
  sudo systemctl restart obegransad
fi
