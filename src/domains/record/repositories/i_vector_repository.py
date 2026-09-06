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

    @abstractmethod
    def search_by_title_keywords(self, query_embedding: list, keywords: list, top_k: int) -> list:
        """제목에 키워드가 들어간 청크만 대상으로 유사도 검색.
        임베딩만으로는 후보군에 들지 못하는 표기(예: 질문은 "유튜브",
        기록은 "YouTube")를 건져오기 위한 보조 경로."""
        raise NotImplementedError

    @abstractmethod
    def search_within_date(self, query_embedding: list, date_from, date_to, top_k: int) -> list:
        """updated_at이 [date_from, date_to) 구간인 청크만 대상으로 유사도 검색.
        구간 내 결과가 없으면 빈 리스트 반환 — 호출부가 search()로 폴백해야 함."""
        raise NotImplementedError

    @abstractmethod
    def search_source_within_date(self, query_embedding: list, source: str, date_from, date_to, top_k: int) -> list:
        """특정 소스 안에서만 날짜 구간 검색 — 다른 소스에 밀리지 않게 따로 뽑을 때 쓴다."""
        raise NotImplementedError

    @abstractmethod
    def list_activity(self) -> list:
        """(source, title, updated_at) 튜플 전체 — 날짜별 일지 생성용"""
        raise NotImplementedError
