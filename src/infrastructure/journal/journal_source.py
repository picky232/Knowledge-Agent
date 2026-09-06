import glob
import os
import re

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


class JournalSource(IDocumentSource):
    """생성된 날짜별 일지를 다시 인덱싱한다.

    원본 기록 수천 건과 달리 하루가 문서 하나라, "어제 뭐 했지" 같은 질문에서
    후보 경쟁 없이 그날 문서가 바로 잡힌다."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def fetch(self) -> list:
        paths = glob.glob(os.path.join(self.base_dir, "*", "*", "*.md"))
        documents = []
        for path in paths:
            day = os.path.splitext(os.path.basename(path))[0]
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            body = FRONTMATTER_RE.sub("", text, count=1).strip()
            if not body:
                continue
            timestamp = f"{day}T12:00:00+09:00"
            documents.append(SourceDocument(
                id=f"journal:{day}",
                source="journal",
                project="활동 일지",
                title=f"{day} 활동 일지",
                url=f"file://{path}",
                content=body,
                created_at=timestamp,
                updated_at=timestamp,
            ))
        return documents
