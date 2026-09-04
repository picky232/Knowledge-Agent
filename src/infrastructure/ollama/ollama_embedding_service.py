import requests

from domains.record.repositories.i_embedding_service import IEmbeddingService


class OllamaEmbeddingService(IEmbeddingService):
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def embed(self, texts: list) -> list:
        resp = requests.post(
            f"{self.host}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]
