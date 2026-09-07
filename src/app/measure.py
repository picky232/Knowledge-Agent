"""응답 시간과 정확도를 함께 재고, 측정 환경이 쓸 만한지 먼저 확인한다.

run_benchmark.py는 벽시계 시간만 기록해서, 메모리가 스왑에 눌린 상태에서 돌리면
평균 187초 같은 숫자가 남고 나중에야 원인을 알게 된다. 여기서는

1. 생성 속도(tok/s)를 먼저 재서 기준 미달이면 측정을 아예 하지 않고,
2. 질문마다 입력·출력 토큰 수를 같이 남긴다.

토큰 수는 메모리 상태와 무관하므로, 검색을 고친 뒤 프롬프트가 커졌는지
줄었는지를 느린 환경에서도 판단할 수 있다.

사용법:
    python3 app/measure.py [질문수]
    python3 app/measure.py --questions 파일.txt
    python3 app/measure.py 30 --accuracy-only   # 느린 환경에서 정확도만 측정
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, container
from app.run_benchmark import build_questions
from domains.record.useCases.ask_question import AskQuestionUseCase
from infrastructure.ollama.instrumented_answer_generator import (
    InstrumentedAnswerGenerator,
    measure_throughput,
)

REPORT_PATH = os.path.join(config.BASE_DIR, "data", "latency_report.jsonl")

# 이 아래로 떨어지면 메모리가 눌린 상태라 어떤 응답 시간을 재도 잡음이다.
# 정상 상태에서 17 tok/s, 스왑 8.7GB 상태에서 4.4 tok/s가 나왔다.
MIN_THROUGHPUT = 12.0

# 근거를 못 찾았을 때 모델이 내놓는 말들. 정확도는 이 비율로 본다.
REFUSAL_MARKERS = ("기록에 없습니다", "찾지 못했습니다", "기록이 없습니다", "관련 기록은 없습니다")


def is_refusal(answer: str) -> bool:
    """첫 문장만 본다.

    답 전체에서 문구를 찾으면 제대로 답하고도 거부로 세어진다. 실제로 모델이
    LifeFivePhoto를 정확히 요약한 뒤 프롬프트의 지시문("기록에 근거가 없으면
    ...")을 그대로 덧붙여 거부로 집계됐다. 프롬프트가 첫 문장에 결론을 쓰라고
    지시하므로, 진짜 거부는 첫 문장이 곧 거부문이다.
    """
    first = answer.strip().replace("\n", ". ").split(". ", 1)[0]
    return any(marker in first for marker in REFUSAL_MARKERS)


def render_bar(done: int, total: int, width: int = 30) -> str:
    filled = int(width * done / total) if total else width
    percent = int(100 * done / total) if total else 100
    return f"[{'█' * filled}{'░' * (width - filled)}] {percent:3d}% ({done}/{total})"


def check_environment() -> float:
    print("측정 환경 점검 중...", flush=True)
    throughput = measure_throughput(config.OLLAMA_HOST, config.ANSWER_MODEL)
    print(f"생성 속도: {throughput} tok/s (기준 {MIN_THROUGHPUT} tok/s)")
    return throughput


def load_questions(argv: list) -> list:
    if len(argv) >= 3 and argv[1] == "--questions":
        with open(argv[2], encoding="utf-8") as fh:
            lines = [line.strip() for line in fh if line.strip()]
        return [{"source": "manual", "title": "", "question": q} for q in lines]

    count = int(argv[1]) if len(argv) > 1 else 30
    return build_questions(count)


def main():
    # 거부율과 토큰 수는 생성 속도와 무관하므로, 환경이 느려도 정확도는 잴 수 있다.
    # 이 모드에서 나온 응답 시간은 보고하지 않는다.
    accuracy_only = "--accuracy-only" in sys.argv

    throughput = check_environment()
    if throughput < MIN_THROUGHPUT and not accuracy_only:
        print(
            f"\n중단합니다. 생성 속도가 {throughput} tok/s로 기준({MIN_THROUGHPUT})에 못 미칩니다.\n"
            "저전력 모드이거나 메모리가 스왑에 눌린 상태에서는 응답 시간을 재도 의미가 없습니다.\n"
            "전원을 연결하고 저전력 모드를 끈 뒤 다시 실행하세요.\n"
            "정확도만 확인하려면 --accuracy-only 를 붙이세요."
        )
        sys.exit(2)
    if accuracy_only:
        print("정확도 측정 모드 — 응답 시간은 참고용으로만 기록합니다.\n")

    questions = load_questions([a for a in sys.argv if a != "--accuracy-only"])
    if not questions:
        print("질문을 만들 데이터가 없습니다. 먼저 sync.py를 실행하세요.")
        sys.exit(1)

    generator = InstrumentedAnswerGenerator(config.OLLAMA_HOST, config.ANSWER_MODEL)
    use_case = AskQuestionUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=generator,
    )

    total = len(questions)
    records = []
    print(f"\n{total}개 질문 측정 시작\n")

    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        for i, item in enumerate(questions, 1):
            start = time.time()
            answer, error = "", None
            try:
                result = use_case.run(item["question"])
                answer = result.answer
            except Exception as exc:
                error = str(exc)
            elapsed = round(time.time() - start, 2)

            stats = generator.last_stats if not error else {}
            record = {
                "index": i,
                "question": item["question"],
                "source": item["source"],
                "answer": answer,
                "refused": is_refusal(answer),
                "elapsed_sec": elapsed,
                "error": error,
                **stats,
            }
            records.append(record)
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()

            mark = "거부" if record["refused"] else ("오류" if error else "답변")
            print(
                f"{render_bar(i, total)} {elapsed:6.2f}s "
                f"입력{stats.get('prompt_tokens', 0):5d} 출력{stats.get('output_tokens', 0):4d} "
                f"{stats.get('tokens_per_sec', 0):5.1f}tok/s {mark}",
                flush=True,
            )

    print_summary(records, throughput, accuracy_only)


def print_summary(records: list, throughput: float, accuracy_only: bool = False):
    ok = [r for r in records if not r["error"]]
    refused = [r for r in ok if r["refused"]]
    answered = [r for r in ok if not r["refused"]]

    def mean(values):
        return round(sum(values) / len(values), 2) if values else 0

    times = [r["elapsed_sec"] for r in ok]
    times_sorted = sorted(times)
    median = times_sorted[len(times_sorted) // 2] if times_sorted else 0
    p90 = times_sorted[int(len(times_sorted) * 0.9)] if times_sorted else 0

    print("\n===== 측정 요약 =====")
    print(f"측정 시작 시점 생성 속도: {throughput} tok/s")
    print(f"질문 {len(records)}건 (오류 {len(records) - len(ok)}건)")
    print(f"답변 {len(answered)}건 / 거부 {len(refused)}건 "
          f"(거부율 {round(100 * len(refused) / len(ok), 1) if ok else 0}%)")
    if accuracy_only:
        print(f"응답 시간  평균 {mean(times)}s (환경 미달 — 참고용, 판정에 쓰지 말 것)")
    else:
        print(f"응답 시간  평균 {mean(times)}s  중앙값 {median}s  p90 {p90}s")
        print(f"4초 이내: {sum(1 for t in times if t <= 4.0)}/{len(times)}건")
    print(f"입력 토큰 평균 {mean([r.get('prompt_tokens', 0) for r in ok])}")
    print(f"출력 토큰 평균 {mean([r.get('output_tokens', 0) for r in ok])}")

    # 시간이 어디서 나가는지 나눠 본다. 어디를 줄여야 하는지가 여기서 갈린다.
    prompt_sec = mean([r.get("prompt_sec", 0) for r in ok])
    generate_sec = mean([r.get("generate_sec", 0) for r in ok])
    retrieval_sec = round(mean(times) - prompt_sec - generate_sec, 2)
    print(f"내역  검색·임베딩 {retrieval_sec}s | 프롬프트 처리 {prompt_sec}s | 생성 {generate_sec}s")
    print(f"상세: {REPORT_PATH}")


if __name__ == "__main__":
    main()
