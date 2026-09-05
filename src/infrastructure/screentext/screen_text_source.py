import json
import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

LOCAL_TZ = ZoneInfo("Asia/Seoul")


class ScreenTextSource(IDocumentSource):
    """watch_screen.py가 남긴 화면 텍스트 로그를 하루 단위 문서로 묶는다.
    로그에는 OCR로 뽑은 텍스트만 들어있고 스크린샷 원본은 캡처 직후 삭제된다."""

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
                by_day[day_key].append((local_ts, entry["app"], entry["text"]))

        documents = []
        for day_key, events in by_day.items():
            events.sort(key=lambda e: e[0])
            sections = [
                f"{ts.strftime('%H:%M')} [{app}]\n{text}"
                for ts, app, text in events
            ]
            documents.append(SourceDocument(
                id=f"screentext:{day_key}",
                source="screen_text",
                project="화면 텍스트 기록",
                title=f"{day_key} 화면 텍스트 기록",
                url="",
                content="\n\n".join(sections),
                created_at=events[0][0].isoformat(),
                updated_at=events[-1][0].isoformat(),
            ))
        return documents
