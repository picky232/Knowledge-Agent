from abc import ABC, abstractmethod


class IDocumentSummarizer(ABC):
    @abstractmethod
    def summarize(self, title: str, content: str) -> str:
        raise NotImplementedError
