import hashlib

from domains.record.entities.record import DocumentChunk
from domains.record.services.chunker import chunk_text

# 일지는 하루치를 요약한 문서라 쪼개면 요약이 있는 앞부분과 목록이 서로 다른
# 청크로 흩어진다. 그러면 검색에서 중간 토막만 뽑혀 정작 요약을 못 본다.
WHOLE_DOCUMENT_SOURCES = {"journal"}


class IndexDocumentsUseCase:
    def __init__(self, sources: list, embedding_service, vector_repository):
        self.sources = sources
        self.embedding_service = embedding_service
        self.vector_repository = vector_repository

    def run(self) -> dict:
        stats = {}
        for source in self.sources:
            source_name = source.__class__.__name__

            try:
                documents = source.fetch()
            except Exception as e:
                stats[source_name] = {"documents": 0, "chunks": 0, "error": str(e)}
                continue

            chunk_count = 0
            failed_docs = 0

            for doc in documents:
                try:
                    chunk_count += self._index_document(doc)
                except Exception:
                    failed_docs += 1

            entry = {"documents": len(documents), "chunks": chunk_count}
            if failed_docs:
                entry["failed_documents"] = failed_docs
            stats[source_name] = entry
        return stats

    def _index_document(self, doc) -> int:
        self.vector_repository.delete_by_document(doc.source, doc.id)
        if doc.source in WHOLE_DOCUMENT_SOURCES:
            pieces = [doc.content] if doc.content.strip() else []
        else:
            pieces = chunk_text(doc.content)
        if not pieces:
            return 0

        embeddings = self.embedding_service.embed(pieces)
        chunks = []
        for i, (piece, emb) in enumerate(zip(pieces, embeddings)):
            chunk_id = hashlib.sha1(f"{doc.id}:{i}".encode()).hexdigest()
            chunks.append(DocumentChunk(
                id=chunk_id,
                document_id=doc.id,
                source=doc.source,
                project=doc.project,
                title=doc.title,
                url=doc.url,
                content=piece,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                embedding=emb,
            ))
        self.vector_repository.add(chunks)
        return len(chunks)
