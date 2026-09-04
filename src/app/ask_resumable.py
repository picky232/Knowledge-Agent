import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import container
from domains.record.useCases.ask_question_resumable import AskQuestionResumableUseCase, make_key


def main():
    if len(sys.argv) < 2:
        print("사용법: python ask_resumable.py \"질문\"")
        print("        (중단됐던 같은 질문을 다시 실행하면 이어서 생성합니다)")
        sys.exit(1)
    question = " ".join(sys.argv[1:])

    state_store = container.build_generation_state_store()
    existing = state_store.load(make_key(question))
    if existing and not existing.done:
        print(f"(이전에 중단된 답변 발견 — 이어서 생성합니다. 지금까지: 생각 {len(existing.thinking_text)}자, 답변 {len(existing.answer_text)}자)")

    use_case = AskQuestionResumableUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=container.build_answer_generator(),
        state_store=state_store,
    )

    def on_answer(delta: str):
        print(delta, end="", flush=True)

    try:
        result = use_case.run(question, think=True, on_answer=on_answer)
    except KeyboardInterrupt:
        print("\n\n중단됨 — 같은 질문으로 다시 실행하면 이어서 생성됩니다.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n오류로 중단됨: {e}")
        print("같은 질문으로 다시 실행하면 이어서 생성됩니다.")
        sys.exit(1)

    print("\n\n출처:")
    seen = set()
    for c in result.citations:
        key = (c.source, c.title, c.url)
        if key in seen:
            continue
        seen.add(key)
        date = c.updated_at[:10] if c.updated_at else "?"
        print(f"  - [{c.source}] {c.title} ({date}) {c.url}")


if __name__ == "__main__":
    main()
