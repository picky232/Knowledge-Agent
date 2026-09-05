import json
import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

LOCAL_TZ = ZoneInfo("Asia/Seoul")


class AppFocusSource(IDocumentSource):
    """watch_focus.py가 남긴 앱 전환 로그(app_focus.jsonl)를 하루 단위
    타임라인 문서로 묶는다. 감시 데몬(kb watch-focus)이 안 켜져 있으면
    로그 파일이 없거나 비어있을 뿐 — 다른 소스에는 영향 없음."""

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
                by_day[day_key].append((local_ts, entry["app"]))

        documents = []
        for day_key, events in by_day.items():
            events.sort(key=lambda e: e[0])
            lines, last_app = [], None
            for ts, app in events:
                if app == last_app:
                    continue
                lines.append(f"{ts.strftime('%H:%M')} {app}")
                last_app = app

            first_ts, last_ts = events[0][0], events[-1][0]
            documents.append(SourceDocument(
                id=f"appfocus:{day_key}",
                source="app_focus",
                project="앱 사용 기록",
                title=f"{day_key} 앱 사용 타임라인",
                url="",
                content="\n".join(lines),
                created_at=first_ts.isoformat(),
                updated_at=last_ts.isoformat(),
            ))
        return documents
