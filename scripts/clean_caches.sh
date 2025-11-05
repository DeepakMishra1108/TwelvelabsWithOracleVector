#!/usr/bin/env bash
# Safe cache cleanup for TwelvelabsVideoAI
# By default this script performs a dry-run. Add --yes to actually delete files.

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILES=(
  "$ROOT_DIR/twelvelabvideoai/upload_tasks.json"
  "$ROOT_DIR/twelvelabvideoai/summary_tasks.json"
  "$ROOT_DIR/twelvelabvideoai/video_task_ids.json"
  "$ROOT_DIR/twelvelabvideoai/.par_cache.json"
  "$ROOT_DIR/server.log"
  "$ROOT_DIR/server.pid"
)
DRY_RUN=true
for arg in "$@"; do
  if [[ "$arg" == "--yes" ]]; then
    DRY_RUN=false
  fi
done

echo "Cache cleanup: dry-run=$DRY_RUN"
for f in "${FILES[@]}"; do
  if [[ -e "$f" ]]; then
    if $DRY_RUN; then
      echo "[dry-run] would remove: $f"
    else
      echo "Removing: $f"
      rm -f -- "$f" || true
    fi
  else
    echo "Not present: $f"
  fi
done

echo "Done."