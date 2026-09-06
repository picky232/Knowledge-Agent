import hashlib

from domains.record.entities.generation_state import GenerationState
from domains.record.entities.record import AnswerResult, DocumentChunk
from domains.record.services.alias_recall import merge_alias_matches
from domains.record.services.date_intent import detect_date_range
from domains.record.services.journal_recall import merge_journal_for_date
from domains.record.services.source_quota import apply_source_quota
from domains.record.services.keyword_boost import boost_by_keyword_overlap, dedup_by_title, prioritize_episodic_sources

CANDIDATE_POOL_SIZE = 50


def make_key(question: str) -> str:
    return hashlib.sha1(question.strip().encode("utf-8")).hexdigest()[:16]


def _chunk_to_dict(c: DocumentChunk) -> dict:
    return {
        "source": c.source, "project": c.project, "title": c.title,
        "url": c.url, "created_at": c.created_at, "updated_at": c.updated_at,
    }


def _dict_to_chunk(d: dict) -> DocumentChunk:
    return DocumentChunk(
        id="", document_id="", source=d["source"], project=d["project"],
        title=d["title"], url=d["url"], content="",
        created_at=d["created_at"], updated_at=d["updated_at"],
    )


class AskQuestionResumableUseCase:
    """중단(타임아웃/많은 요청 대기/Ctrl-C)돼도 같은 질문으로 재실행하면
    이미 생성된 thinking/answer 뒤에서부터 이어서 생성하는 질의 유스케이스."""

    def __init__(self, embedding_service, vector_repository, answer_generator, state_store, top_k: int = 5):
        self.embedding_service = embedding_service
        self.vector_repository = vector_repository
        self.answer_generator = answer_generator
        self.state_store = state_store
        self.top_k = top_k

    def run(self, question: str, think: bool = True, on_thinking=None, on_answer=None) -> AnswerResult:
        key = make_key(question)
        state = self.state_store.load(key)

        if state and not state.done:
            chunks = [_dict_to_chunk(c) for c in state.citations]
        else:
            query_embedding = self.embedding_service.embed([question])[0]

            date_range = detect_date_range(question)
            candidates = []
            used_date_filter = False
            if date_range:
                candidates = self.vector_repository.search_within_date(query_embedding, *date_range, CANDIDATE_POOL_SIZE)
                used_date_filter = bool(candidates)
            if not candidates:
                candidates = self.vector_repository.search(query_embedding, max(self.top_k, CANDIDATE_POOL_SIZE))

            if used_date_filter:
                candidates = prioritize_episodic_sources(candidates)
            candidates = merge_alias_matches(
                self.vector_repository, query_embedding, question, candidates, self.top_k
            )
            candidates = merge_journal_for_date(self.vector_repository, query_embedding, date_range, candidates)
            candidates = apply_source_quota(candidates)
            candidates = dedup_by_title(candidates)
            chunks = boost_by_keyword_overlap(question, candidates, self.top_k)
            state = GenerationState(
                key=key, question=question, stage="answering",
                citations=[_chunk_to_dict(c) for c in chunks],
            )
            self.state_store.save(state)

        def persist_thinking(delta: str):
            state.thinking_text += delta
            self.state_store.save(state)
            if on_thinking:
                on_thinking(delta)

        def persist_answer(delta: str):
            state.answer_text += delta
            self.state_store.save(state)
            if on_answer:
                on_answer(delta)

        try:
            _, answer_text = self.answer_generator.generate_stream(
                question=question,
                context_chunks=chunks,
                think=think,
                resume_thinking=state.thinking_text,
                resume_answer=state.answer_text,
                on_thinking=persist_thinking,
                on_answer=persist_answer,
            )
        except (KeyboardInterrupt, Exception):
            state.done = False
            self.state_store.save(state)
            raise

        state.answer_text = answer_text
        state.done = True
        state.stage = "done"
        self.state_store.save(state)

        return AnswerResult(answer=answer_text, citations=chunks)
