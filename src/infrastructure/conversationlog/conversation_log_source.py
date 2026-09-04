import glob
import json
import os

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

MAX_CONTENT_CHARS = 6000


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
            doc = self._parse_session(path)
            if doc:
                documents.append(doc)
        return documents

    def _parse_session(self, path: str):
        session_id = os.path.splitext(os.path.basename(path))[0]
        ai_title = None
        project = None
        timestamps = []
        text_lines = []

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
                if entry.get("timestamp"):
                    timestamps.append(entry["timestamp"])

                message = entry.get("message", {})
                content = message.get("content", "")
                role = message.get("role", entry_type)

                if isinstance(content, str):
                    if content.strip():
                        text_lines.append(f"{role}: {content.strip()}")
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()
                            if text:
                                text_lines.append(f"{role}: {text}")

        if not text_lines:
            return None

        full_text = "\n".join(text_lines)
        content = full_text[:MAX_CONTENT_CHARS]
        title = ai_title or (project or session_id)

        return SourceDocument(
            id=f"conversation:{session_id}",
            source="conversation",
            project=project or "unknown",
            title=title,
            url=f"file://{path}",
            content=content,
            created_at=min(timestamps) if timestamps else "",
            updated_at=max(timestamps) if timestamps else "",
        )
