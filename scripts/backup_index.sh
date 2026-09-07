#!/bin/bash
# 인덱스(records.db) 백업. 원본 소스에서 다시 만들 수는 있지만
# 전체 재인덱싱에 수십 분이 걸리므로, 날짜별로 몇 벌 남겨둔다.
set -euo pipefail

PROJECT_DIR="/Users/jiho0215/knowledge-agent"
DB="$PROJECT_DIR/data/records.db"
BACKUP_DIR="$PROJECT_DIR/data/backups"
KEEP=5

[ -s "$DB" ] || { echo "백업할 인덱스가 없습니다: $DB"; exit 1; }

mkdir -p "$BACKUP_DIR"
STAMP=$(date '+%Y%m%d-%H%M')
# .backup은 다른 프로세스가 쓰는 중이어도 일관된 사본을 만든다
sqlite3 "$DB" ".backup '$BACKUP_DIR/records-$STAMP.db'"

# 오래된 백업 정리
ls -1t "$BACKUP_DIR"/records-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    rm -f "$old"
done

echo "백업 완료: $BACKUP_DIR/records-$STAMP.db ($(ls -1 "$BACKUP_DIR" | wc -l | tr -d ' ')벌 보관)"
