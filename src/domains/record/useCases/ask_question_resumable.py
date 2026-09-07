import hashlib

from domains.record.entities.generation_state import GenerationState
from domains.record.entities.record import AnswerResult, DocumentChunk
from domains.record.services.retrieval_pipeline import CANDIDATE_POOL_SIZE, retrieve


def make_key(question: str) -> str:
    return hashlib.sha1(question.strip().encode("utf-8")).hexdigest()[:16]


def _chunk_to_dict(c: DocumentChunk) -> dict:
    # 본문까지 저장한다. 이걸 빼면 이어쓰기할 때 프롬프트의 [기록]이 제목만 남은
    # 껍데기가 되어, 모델이 근거 없이 앞 문장을 이어 쓴다. 조각 다섯 개면
    # 3~4KB라 상태 파일이 커지는 부담은 없다.
    return {
        "source": c.source, "project": c.project, "title": c.title,
        "url": c.url, "content": c.content,
        "created_at": c.created_at, "updated_at": c.updated_at,
    }


def _dict_to_chunk(d: dict) -> DocumentChunk:
    # content는 예전 상태 파일에는 없다. 그때는 빈 문자열로 두고 이어서 생성한다 —
    # 근거가 없는 채로 이어지지만, 파일을 읽다 죽는 것보다는 낫다.
    return DocumentChunk(
        id="", document_id="", source=d["source"], project=d["project"],
        title=d["title"], url=d["url"], content=d.get("content", ""),
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
            chunks = retrieve(
                self.vector_repository, self.embedding_service, question,
                self.top_k, CANDIDATE_POOL_SIZE,
            )
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
