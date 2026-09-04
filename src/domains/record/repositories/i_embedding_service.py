from abc import ABC, abstractmethod


class IEmbeddingService(ABC):
    @abstractmethod
    def embed(self, texts: list) -> list:
        """텍스트 리스트 -> 임베딩 벡터 리스트"""
        raise NotImplementedError
