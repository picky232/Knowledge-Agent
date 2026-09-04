from abc import ABC, abstractmethod


class IVectorRepository(ABC):
    @abstractmethod
    def add(self, chunks: list) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query_embedding: list, top_k: int) -> list:
        """DocumentChunk 리스트, 유사도 높은 순"""
        raise NotImplementedError

    @abstractmethod
    def delete_by_document(self, source: str, document_id: str) -> None:
        """재인덱싱 전 같은 문서의 기존 청크 제거"""
        raise NotImplementedError
