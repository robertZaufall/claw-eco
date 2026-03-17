#!/bin/zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="$HOME/git/claw-eco"
LOG_DIR="$REPO/.logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily-update-$(date +%F).log"

exec >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Starting claw-eco daily update"

cd "$REPO"

python3 update_stats.py --file index.html

if git diff --quiet -- index.html; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] No changes in index.html; nothing to commit"
  exit 0
fi

git add index.html

git commit -m "chore: update claw-eco stats ($(date +%F))"

git push origin main

echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Update committed and pushed"
