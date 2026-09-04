import json
import os
from dataclasses import asdict
from typing import Optional

from domains.record.entities.generation_state import GenerationState
from domains.record.repositories.i_generation_state_store import IGenerationStateStore


class FileGenerationStateStore(IGenerationStateStore):
    def __init__(self, dir_path: str):
        self.dir_path = dir_path
        os.makedirs(self.dir_path, exist_ok=True)

    def load(self, key: str) -> Optional[GenerationState]:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return GenerationState(**data)

    def save(self, state: GenerationState) -> None:
        path = self._path(state.key)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(asdict(state), fh, ensure_ascii=False)
        os.replace(tmp_path, path)

    def clear(self, key: str) -> None:
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def _path(self, key: str) -> str:
        return os.path.join(self.dir_path, f"{key}.json")
