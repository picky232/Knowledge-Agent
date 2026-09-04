import hashlib

from domains.record.entities.record import DocumentChunk
from domains.record.services.chunker import chunk_text


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
