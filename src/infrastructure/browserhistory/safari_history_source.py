import hashlib
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

SAFARI_EPOCH_OFFSET = 978307200  # 2001-01-01 -> 1970-01-01 초 차이

PERMISSION_HINT = (
    "Safari 히스토리 접근 권한 없음 — "
    "시스템 설정 > 개인정보 보호 및 보안 > 전체 디스크 접근 권한에서 "
    "이 스크립트를 실행하는 터미널 앱을 추가해야 합니다."
)


def _safari_time_to_iso(mac_absolute_time: float) -> str:
    unix_seconds = mac_absolute_time + SAFARI_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).isoformat()


class SafariHistorySource(IDocumentSource):
    def __init__(self, lookback_days: int = 30, max_entries: int = 500, db_path: str = None):
        self.lookback_days = lookback_days
        self.max_entries = max_entries
        self.db_path = db_path or os.path.expanduser("~/Library/Safari/History.db")

    def fetch(self) -> list:
        if not os.path.exists(self.db_path):
            return []

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_db = os.path.join(tmp_dir, "History.db")
                shutil.copy2(self.db_path, tmp_db)
                for suffix in ("-wal", "-shm"):
                    side = self.db_path + suffix
                    if os.path.exists(side):
                        shutil.copy2(side, tmp_db + suffix)

                cutoff_mac_time = (
                    datetime.now(timezone.utc) - timedelta(days=self.lookback_days)
                ).timestamp() - SAFARI_EPOCH_OFFSET

                conn = sqlite3.connect(tmp_db)
                try:
                    rows = conn.execute(
                        """SELECT hi.url, hv.title, hi.visit_count, MAX(hv.visit_time)
                           FROM history_items hi
                           JOIN history_visits hv ON hv.history_item = hi.id
                           WHERE hv.visit_time >= ? AND hv.title IS NOT NULL AND hv.title != ''
                           GROUP BY hi.url
                           ORDER BY MAX(hv.visit_time) DESC
                           LIMIT ?""",
                        (cutoff_mac_time, self.max_entries),
                    ).fetchall()
                finally:
                    conn.close()
        except (PermissionError, sqlite3.OperationalError) as e:
            raise PermissionError(PERMISSION_HINT) from e

        documents = []
        for url, title, visit_count, visit_time in rows:
            url_hash = hashlib.sha1(url.encode()).hexdigest()[:16]
            visited_at = _safari_time_to_iso(visit_time)
            domain = urlparse(url).netloc
            documents.append(SourceDocument(
                id=f"safari:{url_hash}",
                source="browser_history",
                project="Safari",
                title=title or url,
                url=url,
                content=f"{title}\n{domain}\n방문 횟수: {visit_count}",
                created_at=visited_at,
                updated_at=visited_at,
            ))
        return documents
