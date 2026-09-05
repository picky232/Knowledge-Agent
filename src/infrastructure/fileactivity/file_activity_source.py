import json
import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

LOCAL_TZ = ZoneInfo("Asia/Seoul")


class FileActivitySource(IDocumentSource):
    """watch_files.py가 남긴 파일 활동 로그를 하루 단위 문서로 묶는다.
    "그 파일 언제 작업했지" 류 질의에 답하기 위한 소스."""

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
                by_day[day_key].append((local_ts, entry["project"], entry["path"], entry["action"]))

        documents = []
        for day_key, events in by_day.items():
            events.sort(key=lambda e: e[0])

            by_project = defaultdict(list)
            for ts, project, path, action in events:
                by_project[project].append(f"{ts.strftime('%H:%M')} {path} ({action})")

            sections = []
            for project, lines in by_project.items():
                sections.append(f"[{project}]\n" + "\n".join(lines))

            documents.append(SourceDocument(
                id=f"fileactivity:{day_key}",
                source="file_activity",
                project="파일 작업 기록",
                title=f"{day_key} 파일 작업 기록",
                url="",
                content="\n\n".join(sections),
                created_at=events[0][0].isoformat(),
                updated_at=events[-1][0].isoformat(),
            ))
        return documents
