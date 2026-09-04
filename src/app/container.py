import os

from app import config
from infrastructure.browserhistory.chrome_history_source import ChromeHistorySource
from infrastructure.browserhistory.safari_history_source import SafariHistorySource
from infrastructure.conversationlog.conversation_log_source import ConversationLogSource
from infrastructure.github.github_source import GithubSource
from infrastructure.notion.notion_source import NotionSource
from infrastructure.ollama.ollama_answer_generator import OllamaAnswerGenerator
from infrastructure.ollama.ollama_embedding_service import OllamaEmbeddingService
from infrastructure.resume.file_generation_state_store import FileGenerationStateStore
from infrastructure.vectorstore.sqlite_vector_repository import SqliteVectorRepository
from infrastructure.websearch.websearch_log_source import WebSearchLogSource

WEBSEARCH_LOG_PATH = os.path.join(config.BASE_DIR, "data", "websearch.jsonl")
PARTIAL_ANSWERS_DIR = os.path.join(config.BASE_DIR, "data", "partial_answers")


def build_sources() -> list:
    sources = [
        GithubSource(limit_repos=20),
        ConversationLogSource(limit_sessions=30),
        WebSearchLogSource(log_path=WEBSEARCH_LOG_PATH),
        ChromeHistorySource(lookback_days=30),
        SafariHistorySource(lookback_days=30),
    ]
    if config.NOTION_TOKEN:
        sources.append(NotionSource(token=config.NOTION_TOKEN))
    else:
        print("(Notion 토큰 없음 — Notion 소스 건너뜀)")
    return sources


def build_embedding_service() -> OllamaEmbeddingService:
    return OllamaEmbeddingService(config.OLLAMA_HOST, config.EMBED_MODEL)


def build_vector_repository() -> SqliteVectorRepository:
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    return SqliteVectorRepository(config.DB_PATH)


def build_answer_generator() -> OllamaAnswerGenerator:
    return OllamaAnswerGenerator(config.OLLAMA_HOST, config.ANSWER_MODEL)


def build_generation_state_store() -> FileGenerationStateStore:
    return FileGenerationStateStore(PARTIAL_ANSWERS_DIR)
