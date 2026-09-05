import json
import sqlite3
from datetime import datetime

import numpy as np

from domains.record.entities.record import DocumentChunk
from domains.record.repositories.i_vector_repository import IVectorRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    source TEXT NOT NULL,
    project TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    embedding TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(source, document_id);
"""


class SqliteVectorRepository(IVectorRepository):
    def __init__(self, db_path: str):
        self.db_path = db_path
        conn = sqlite3.connect(self.db_path)
        conn.executescript(SCHEMA)
        conn.commit()
        conn.close()

    def add(self, chunks: list) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            """INSERT OR REPLACE INTO chunks
               (id, document_id, source, project, title, url, content, created_at, updated_at, embedding)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    c.id, c.document_id, c.source, c.project, c.title, c.url,
                    c.content, c.created_at, c.updated_at, json.dumps(c.embedding),
                )
                for c in chunks
            ],
        )
        conn.commit()
        conn.close()

    def delete_by_document(self, source: str, document_id: str) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "DELETE FROM chunks WHERE source = ? AND document_id = ?",
            (source, document_id),
        )
        conn.commit()
        conn.close()

    def list_projects(self) -> list:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """SELECT source, project, COUNT(*), MAX(updated_at)
               FROM chunks GROUP BY source, project"""
        ).fetchall()
        conn.close()
        return rows

    def get_project_content(self, source: str, project: str, max_chars: int) -> str:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            """SELECT DISTINCT title, content FROM chunks
               WHERE source = ? AND project = ? ORDER BY document_id, id""",
            (source, project),
        ).fetchall()
        conn.close()

        parts, total = [], 0
        for title, content in rows:
            piece = f"[{title}]\n{content}"
            if total + len(piece) > max_chars:
                break
            parts.append(piece)
            total += len(piece)
        return "\n\n".join(parts)

    def search(self, query_embedding: list, top_k: int) -> list:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, document_id, source, project, title, url, content, created_at, updated_at, embedding FROM chunks"
        ).fetchall()
        conn.close()
        return self._rank_rows(rows, query_embedding, top_k)

    def search_by_title_keywords(self, query_embedding: list, keywords: list, top_k: int) -> list:
        if not keywords:
            return []

        conditions = " OR ".join(["lower(title) LIKE ?"] * len(keywords))
        params = [f"%{k.lower()}%" for k in keywords]
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, document_id, source, project, title, url, content, "
            f"created_at, updated_at, embedding FROM chunks WHERE {conditions}",
            params,
        ).fetchall()
        conn.close()
        return self._rank_rows(rows, query_embedding, top_k)

    def search_within_date(self, query_embedding: list, date_from, date_to, top_k: int) -> list:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, document_id, source, project, title, url, content, created_at, updated_at, embedding FROM chunks"
        ).fetchall()
        conn.close()

        filtered = []
        for row in rows:
            try:
                updated = datetime.fromisoformat(row[8].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue
            if date_from <= updated < date_to:
                filtered.append(row)

        return self._rank_rows(filtered, query_embedding, top_k)

    def _rank_rows(self, rows: list, query_embedding: list, top_k: int) -> list:
        if not rows:
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec) or 1.0

        scored = []
        for row in rows:
            emb = np.array(json.loads(row[9]), dtype=np.float32)
            emb_norm = np.linalg.norm(emb) or 1.0
            similarity = float(np.dot(query_vec, emb) / (query_norm * emb_norm))
            scored.append((similarity, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            DocumentChunk(
                id=row[0], document_id=row[1], source=row[2], project=row[3],
                title=row[4], url=row[5], content=row[6],
                created_at=row[7], updated_at=row[8], embedding=None,
            )
            for _, row in scored[:top_k]
        ]
