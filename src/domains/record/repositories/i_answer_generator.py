from abc import ABC, abstractmethod


class IAnswerGenerator(ABC):
    @abstractmethod
    def generate(self, question: str, context_chunks: list) -> str:
        raise NotImplementedError
