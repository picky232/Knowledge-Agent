#!/bin/bash
set -euo pipefail

PROJECT_DIR="/Users/jiho0215/knowledge-agent"
LOG_FILE="$PROJECT_DIR/logs/sync.log"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') sync start =====" >> "$LOG_FILE"
cd "$PROJECT_DIR/src"
"$PROJECT_DIR/.venv/bin/python3" app/sync.py >> "$LOG_FILE" 2>&1
echo "===== $(date '+%Y-%m-%d %H:%M:%S') sync end =====" >> "$LOG_FILE"
