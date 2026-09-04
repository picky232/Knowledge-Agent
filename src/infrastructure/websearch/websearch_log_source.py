import json
import os

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource


class WebSearchLogSource(IDocumentSource):
    def __init__(self, log_path: str):
        self.log_path = log_path

    def fetch(self) -> list:
        if not os.path.exists(self.log_path):
            return []

        documents = []
        with open(self.log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                content = "\n".join(filter(None, [entry.get("query", ""), entry.get("note", "")]))
                documents.append(SourceDocument(
                    id=f"websearch:{entry['id']}",
                    source="websearch",
                    project="웹서칭 기록",
                    title=entry.get("query", "(제목 없음)"),
                    url=entry.get("url", ""),
                    content=content or entry.get("query", ""),
                    created_at=entry.get("timestamp", ""),
                    updated_at=entry.get("timestamp", ""),
                ))
        return documents
