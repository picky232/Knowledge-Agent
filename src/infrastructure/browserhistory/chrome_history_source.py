import glob
import hashlib
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

CHROME_EPOCH_OFFSET = 11644473600  # 1601-01-01 -> 1970-01-01 초 차이


def _chrome_time_to_iso(chrome_micros: int) -> str:
    unix_seconds = chrome_micros / 1_000_000 - CHROME_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc).isoformat()


class ChromeHistorySource(IDocumentSource):
    def __init__(self, lookback_days: int = 30, max_per_profile: int = 500, base_dir: str = None):
        self.lookback_days = lookback_days
        self.max_per_profile = max_per_profile
        self.base_dir = base_dir or os.path.expanduser(
            "~/Library/Application Support/Google/Chrome"
        )

    def fetch(self) -> list:
        history_files = glob.glob(os.path.join(self.base_dir, "*", "History"))
        if not history_files:
            return []

        documents = []
        for history_path in history_files:
            profile_name = os.path.basename(os.path.dirname(history_path))
            documents.extend(self._fetch_profile(profile_name, history_path))
        return documents

    def _fetch_profile(self, profile_name: str, history_path: str) -> list:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_db = os.path.join(tmp_dir, "History")
            shutil.copy2(history_path, tmp_db)
            for suffix in ("-wal", "-shm"):
                side = history_path + suffix
                if os.path.exists(side):
                    shutil.copy2(side, tmp_db + suffix)

            cutoff_chrome_time = int(
                ((datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).timestamp()
                 + CHROME_EPOCH_OFFSET) * 1_000_000
            )

            conn = sqlite3.connect(tmp_db)
            try:
                rows = conn.execute(
                    """SELECT url, title, visit_count, last_visit_time
                       FROM urls
                       WHERE last_visit_time >= ? AND title != ''
                       ORDER BY last_visit_time DESC
                       LIMIT ?""",
                    (cutoff_chrome_time, self.max_per_profile),
                ).fetchall()
            finally:
                conn.close()

        documents = []
        for url, title, visit_count, last_visit_time in rows:
            url_hash = hashlib.sha1(url.encode()).hexdigest()[:16]
            visited_at = _chrome_time_to_iso(last_visit_time)
            domain = urlparse(url).netloc
            documents.append(SourceDocument(
                id=f"chrome:{profile_name}:{url_hash}",
                source="browser_history",
                project=f"Chrome/{profile_name}",
                title=title,
                url=url,
                content=f"{title}\n{domain}\n방문 횟수: {visit_count}",
                created_at=visited_at,
                updated_at=visited_at,
            ))
        return documents
