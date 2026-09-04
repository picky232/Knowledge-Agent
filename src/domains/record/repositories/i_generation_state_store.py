from abc import ABC, abstractmethod
from typing import Optional


class IGenerationStateStore(ABC):
    @abstractmethod
    def load(self, key: str) -> Optional["GenerationState"]:
        raise NotImplementedError

    @abstractmethod
    def save(self, state: "GenerationState") -> None:
        raise NotImplementedError

    @abstractmethod
    def clear(self, key: str) -> None:
        raise NotImplementedError
