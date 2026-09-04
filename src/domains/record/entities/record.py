from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceDocument:
    id: str
    source: str
    project: str
    title: str
    url: str
    content: str
    created_at: str
    updated_at: str


@dataclass
class DocumentChunk:
    id: str
    document_id: str
    source: str
    project: str
    title: str
    url: str
    content: str
    created_at: str
    updated_at: str
    embedding: Optional[list] = field(default=None)


@dataclass
class AnswerResult:
    answer: str
    citations: list
