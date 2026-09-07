#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/jiho0215/knowledge-agent"
LOG_FILE="$PROJECT_DIR/logs/sync.log"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') sync start =====" >> "$LOG_FILE"
# 인덱싱 전에 현재 인덱스를 백업해둔다 — 동기화가 중간에 깨져도 되돌릴 수 있게
"$PROJECT_DIR/scripts/backup_index.sh" >> "$LOG_FILE" 2>&1 || true

cd "$PROJECT_DIR/src"
"$PROJECT_DIR/.venv/bin/python3" app/sync.py >> "$LOG_FILE" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') sync end =====" >> "$LOG_FILE"
