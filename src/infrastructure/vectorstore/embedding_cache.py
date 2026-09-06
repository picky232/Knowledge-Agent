"""임베딩 행렬을 메모리에 올려두는 캐시.

매 검색마다 SQLite에서 수천 건의 임베딩을 읽어 JSON으로 파싱하면
검색 자체보다 그 준비 과정이 더 오래 걸린다. 한 번 읽어 numpy 행렬로
만들어두면 이후 검색은 행렬 곱 한 번으로 끝난다.
"""

import json
import os
import sqlite3

import numpy as np

COLUMNS = "id, document_id, source, project, title, url, content, created_at, updated_at"


class EmbeddingCache:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._matrix = None
        self._rows = None
        self._norms = None
        self._signature = None

    def _current_signature(self):
        """행 수와 파일 수정 시각으로 인덱스가 바뀌었는지 판단한다."""
        try:
            mtime = os.path.getmtime(self.db_path)
        except OSError:
            mtime = 0
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        conn.close()
        return (count, mtime)

    def load(self):
        """(rows, matrix, norms)을 돌려준다. 인덱스가 바뀌었으면 다시 읽는다."""
        signature = self._current_signature()
        if self._matrix is not None and signature == self._signature:
            return self._rows, self._matrix, self._norms

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(f"SELECT {COLUMNS}, embedding FROM chunks").fetchall()
        conn.close()

        if not rows:
            self._rows, self._matrix, self._norms = [], None, None
            self._signature = signature
            return self._rows, self._matrix, self._norms

        vectors = np.array([json.loads(r[-1]) for r in rows], dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1)
        norms[norms == 0] = 1.0

        self._rows = [r[:-1] for r in rows]
        self._matrix = vectors
        self._norms = norms
        self._signature = signature
        return self._rows, self._matrix, self._norms
