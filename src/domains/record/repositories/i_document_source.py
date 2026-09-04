from abc import ABC, abstractmethod


class IDocumentSource(ABC):
    @abstractmethod
    def fetch(self) -> list:
        """SourceDocument 리스트 반환"""
        raise NotImplementedError
