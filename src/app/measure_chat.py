"""채팅창에서 실제로 느끼는 지연을 잰다.

`measure.py`는 답변이 다 만들어질 때까지의 시간을 잰다. 그런데 채팅창(빠른 질문
창·GUI·브라우저)은 전부 SSE로 토큰을 흘려보내므로, 사용자가 기다리는 시간은
**첫 글자가 뜰 때까지**다. 그 뒤로는 글이 이어서 나온다.

그리고 채팅창은 `AskQuestionUseCase`가 아니라 `AskQuestionResumableUseCase`를
쓴다. 측정 대상이 실제 경로와 달라지지 않도록 여기서는 재개형을 그대로 쓴다.

`think`를 바꿔가며 재면 추론 생성이 첫 글자를 얼마나 늦추는지 알 수 있다.

사용법:
    python3 app/measure_chat.py [질문수]
    python3 app/measure_chat.py 10 --think            # 추론 켠 상태로 측정
    python3 app/measure_chat.py 10 --model gemma3:4b  # 다른 모델로 같은 조건 비교
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, container
from app.measure import MIN_THROUGHPUT, is_refusal, render_bar
from app.run_benchmark import build_questions
from domains.record.useCases.ask_question_resumable import AskQuestionResumableUseCase, make_key
from infrastructure.ollama.instrumented_answer_generator import measure_throughput
from infrastructure.ollama.ollama_answer_generator import OllamaAnswerGenerator

REPORT_PATH = os.path.join(config.BASE_DIR, "data", "chat_latency_report.jsonl")


def measure_one(use_case, state_store, question: str, think: bool) -> dict:
    # 같은 질문을 다시 물으면 저장된 생성 상태를 이어받아 즉시 끝난다.
    # 측정에서는 매번 처음부터 만들어야 하므로 지운다.
    state_store.clear(make_key(question))

    start = time.time()
    first_token_at = [None]

    def on_answer(_delta: str):
        if first_token_at[0] is None:
            first_token_at[0] = time.time() - start

    answer, error = "", None
    try:
        answer = use_case.run(question, think=think, on_answer=on_answer).answer
    except Exception as exc:
        error = str(exc)

    return {
        "question": question,
        "think": think,
        "answer": answer,
        "refused": is_refusal(answer),
        "first_token_sec": round(first_token_at[0], 2) if first_token_at[0] else None,
        "total_sec": round(time.time() - start, 2),
        "error": error,
    }


def parse_model(argv: list) -> str:
    """--model NAME 이 있으면 그 모델로, 없으면 설정된 답변 모델로."""
    if "--model" in argv:
        index = argv.index("--model")
        if index + 1 < len(argv):
            return argv[index + 1]
    return config.ANSWER_MODEL


def main():
    think = "--think" in sys.argv
    model = parse_model(sys.argv)
    skip = {"--model", model}
    args = [a for a in sys.argv[1:] if not a.startswith("-") and a not in skip]
    count = int(args[0]) if args else 10

    throughput = measure_throughput(config.OLLAMA_HOST, model)
    print(f"생성 속도 {throughput} tok/s", end="")
    print(" — 측정 가능" if throughput >= MIN_THROUGHPUT else f" — 기준 {MIN_THROUGHPUT} 미만, 참고용")

    questions = build_questions(count)
    if not questions:
        print("인덱싱된 데이터가 없습니다. 먼저 sync.py를 실행하세요.")
        sys.exit(1)

    state_store = container.build_generation_state_store()
    use_case = AskQuestionResumableUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=OllamaAnswerGenerator(config.OLLAMA_HOST, model),
        state_store=state_store,
    )

    print(f"\n채팅 경로 {len(questions)}건 측정 — {model} (추론 {'켬' if think else '끔'})\n")
    records = []
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        for i, item in enumerate(questions, 1):
            record = measure_one(use_case, state_store, item["question"], think)
            records.append(record)
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            first = record["first_token_sec"]
            print(
                f"{render_bar(i, len(questions))} 첫글자 "
                f"{first if first is not None else '--':>6}s 전체 {record['total_sec']:6.2f}s",
                flush=True,
            )

    print_summary(records, throughput, think, model)


def print_summary(records: list, throughput: float, think: bool, model: str = ""):
    ok = [r for r in records if not r["error"] and r["first_token_sec"] is not None]
    if not ok:
        print("\n측정된 응답이 없습니다.")
        return

    firsts = sorted(r["first_token_sec"] for r in ok)
    totals = sorted(r["total_sec"] for r in ok)

    def mean(v):
        return round(sum(v) / len(v), 2)

    print(f"\n===== 채팅 체감 지연 — {model} (추론 {'켬' if think else '끔'}) =====")
    print(f"측정 시작 시점 생성 속도: {throughput} tok/s")
    print(f"첫 글자까지  평균 {mean(firsts)}s  중앙값 {firsts[len(firsts) // 2]}s  최대 {firsts[-1]}s")
    print(f"전체 완성까지 평균 {mean(totals)}s  중앙값 {totals[len(totals) // 2]}s")
    print(f"첫 글자 4초 이내: {sum(1 for t in firsts if t <= 4.0)}/{len(firsts)}건")
    print(f"거부 {sum(1 for r in ok if r['refused'])}건")
    print(f"상세: {REPORT_PATH}")


if __name__ == "__main__":
    main()
