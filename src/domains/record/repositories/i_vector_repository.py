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

    @abstractmethod
    def list_projects(self) -> list:
        """(source, project, chunk_count, max_updated_at) 튜플 리스트 — 요약 인덱스 생성용"""
        raise NotImplementedError

    @abstractmethod
    def get_project_content(self, source: str, project: str, max_chars: int) -> str:
        """해당 프로젝트에 속한 청크 content를 이어붙인 텍스트 — 요약 인풋"""
        raise NotImplementedError
