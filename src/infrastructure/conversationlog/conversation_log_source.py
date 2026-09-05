import glob
import json
import os
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

MAX_CONTENT_CHARS_PER_DAY = 20000
LOCAL_TZ = ZoneInfo("Asia/Seoul")


class ConversationLogSource(IDocumentSource):
    def __init__(self, projects_dir: str = None, limit_sessions: int = 30):
        self.projects_dir = projects_dir or os.path.expanduser("~/.claude/projects")
        self.limit_sessions = limit_sessions

    def fetch(self) -> list:
        files = glob.glob(os.path.join(self.projects_dir, "*", "*.jsonl"))
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        files = files[: self.limit_sessions]

        documents = []
        for path in files:
            documents.extend(self._parse_session(path))
        return documents

    def _parse_session(self, path: str) -> list:
        """세션 하나를 통째로 자르지 않고, 대화가 걸쳐있는 날짜별로 문서를 나눈다.
        오래 이어진 세션(몇 MB짜리)도 앞부분만 자르면 최근 내용이 통째로
        빠지는 문제가 있어서, 날짜별 청크는 각각 넉넉한 한도만 두고 전부 보존."""
        session_id = os.path.splitext(os.path.basename(path))[0]
        ai_title = None
        project = None
        entries_by_day = defaultdict(list)

        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                entry_type = entry.get("type")

                if entry_type == "ai-title" and not ai_title:
                    ai_title = entry.get("aiTitle")
                    continue

                if entry_type not in ("user", "assistant"):
                    continue

                if not project and entry.get("cwd"):
                    project = os.path.basename(entry["cwd"])

                timestamp = entry.get("timestamp")
                if not timestamp:
                    continue
                try:
                    ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
                day_key = ts.astimezone(LOCAL_TZ).date().isoformat()

                message = entry.get("message", {})
                content = message.get("content", "")
                role = message.get("role", entry_type)

                texts = []
                if isinstance(content, str):
                    if content.strip():
                        texts.append(content.strip())
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()
                            if text:
                                texts.append(text)

                for text in texts:
                    entries_by_day[day_key].append((timestamp, f"{role}: {text}"))

        if not entries_by_day:
            return []

        title_base = ai_title or (project or session_id)
        documents = []
        for day_key, entries in entries_by_day.items():
            entries.sort(key=lambda e: e[0])
            day_text = "\n".join(text for _, text in entries)[:MAX_CONTENT_CHARS_PER_DAY]
            documents.append(SourceDocument(
                id=f"conversation:{session_id}:{day_key}",
                source="conversation",
                project=project or "unknown",
                title=f"{title_base} ({day_key})",
                url=f"file://{path}",
                content=day_text,
                created_at=entries[0][0],
                updated_at=entries[-1][0],
            ))
        return documents
