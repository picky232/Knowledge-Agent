from abc import ABC, abstractmethod
from typing import Optional


class IIndexWriter(ABC):
    @abstractmethod
    def read_topic_updated_at(self, source: str, project: str) -> Optional[str]:
        raise NotImplementedError

    @abstractmethod
    def read_topic_summary(self, source: str, project: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def write_topic(self, source: str, project: str, summary: str, chunk_count: int, updated_at: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def write_root_index(self, entries: list) -> str:
        raise NotImplementedError
