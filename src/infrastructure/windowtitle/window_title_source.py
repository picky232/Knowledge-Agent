import json
import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

LOCAL_TZ = ZoneInfo("Asia/Seoul")


class WindowTitleSource(IDocumentSource):
    """watch_window.py가 남긴 창 제목 로그(window_title.jsonl)를 하루 단위
    타임라인 문서로 묶는다. Accessibility 권한이 없으면 감시 데몬이 로그를
    안 남길 뿐 — 로그 파일이 없으면 조용히 빈 리스트 반환."""

    def __init__(self, log_path: str):
        self.log_path = log_path

    def fetch(self) -> list:
        if not os.path.exists(self.log_path):
            return []

        by_day = defaultdict(list)
        with open(self.log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = datetime.fromisoformat(entry["timestamp"])
                local_ts = ts.astimezone(LOCAL_TZ)
                day_key = local_ts.date().isoformat()
                by_day[day_key].append((local_ts, entry["app"], entry["title"]))

        documents = []
        for day_key, events in by_day.items():
            events.sort(key=lambda e: e[0])
            lines = [f"{ts.strftime('%H:%M')} [{app}] {title}" for ts, app, title in events]

            first_ts, last_ts = events[0][0], events[-1][0]
            documents.append(SourceDocument(
                id=f"windowtitle:{day_key}",
                source="window_title",
                project="창 제목 기록",
                title=f"{day_key} 창 제목 타임라인",
                url="",
                content="\n".join(lines),
                created_at=first_ts.isoformat(),
                updated_at=last_ts.isoformat(),
            ))
        return documents
