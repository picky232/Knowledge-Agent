import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

LOCAL_TZ = ZoneInfo("Asia/Seoul")


def append_turn(log_path: str, question: str, answer: str) -> None:
    """에이전트와 나눈 대화 한 턴을 기록한다.
    화면에서는 매번 지워지지만, 무엇을 찾아봤는지 자체가 기록이므로 남긴다."""
    entry = {
        "question": question,
        "answer": answer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


class ChatLogSource(IDocumentSource):
    """에이전트와 나눈 대화를 날짜별 문서로 묶어 다시 검색 대상으로 만든다."""

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
                ts = datetime.fromisoformat(entry["timestamp"]).astimezone(LOCAL_TZ)
                by_day[ts.date().isoformat()].append((ts, entry))

        documents = []
        for day, turns in by_day.items():
            turns.sort(key=lambda t: t[0])
            body = "\n\n".join(
                f"{ts.strftime('%H:%M')} 질문: {e['question']}\n답변: {e['answer']}"
                for ts, e in turns
            )
            documents.append(SourceDocument(
                id=f"chatlog:{day}",
                source="chat_log",
                project="에이전트 대화",
                title=f"{day} 에이전트에게 물어본 것",
                url="",
                content=body,
                created_at=turns[0][0].isoformat(),
                updated_at=turns[-1][0].isoformat(),
            ))
        return documents
