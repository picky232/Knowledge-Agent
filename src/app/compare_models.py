"""같은 질문 묶음을 두 모델에 돌려 정확도와 속도를 나란히 비교한다.

qwen3:8b는 통합 메모리 5,660MB를 wired로 붙잡는다(모델을 내렸다 올리며 실측:
8,039M → 2,379M). 16GB 머신에서 사용자 앱이 9GB를 쓰는 상태라 모델까지 올리면
한도를 넘겨 스왑으로 밀린다. 더 작은 모델로 바꾸면 이 압박이 사라지지만,
답을 못 찾게 되면 의미가 없다. 그래서 응답 시간만 보지 않고 거부율을 같이 잰다.

검색 단계는 두 모델이 완전히 같은 것을 쓴다. 임베딩 모델도, 인덱스도, 후보
선정 로직도 동일하다. 달라지는 것은 생성뿐이므로 차이는 모델 탓으로 볼 수 있다.

사용법:
    python3 app/compare_models.py qwen3:8b qwen3:4b [질문수]
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, container
from app.measure import MIN_THROUGHPUT, is_refusal, render_bar
from app.run_benchmark import build_questions
from domains.record.useCases.ask_question import AskQuestionUseCase
from infrastructure.ollama.instrumented_answer_generator import (
    InstrumentedAnswerGenerator,
    measure_throughput,
)

REPORT_PATH = os.path.join(config.BASE_DIR, "data", "model_comparison.jsonl")


def run_model(model: str, questions: list, fh) -> dict:
    """한 모델로 전체 질문을 돌리고 집계를 돌려준다."""
    generator = InstrumentedAnswerGenerator(config.OLLAMA_HOST, model)
    use_case = AskQuestionUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=generator,
    )

    total = len(questions)
    records = []
    print(f"\n--- {model} ---")

    for i, item in enumerate(questions, 1):
        start = time.time()
        answer, error = "", None
        try:
            answer = use_case.run(item["question"]).answer
        except Exception as exc:
            error = str(exc)
        elapsed = round(time.time() - start, 2)

        stats = generator.last_stats if not error else {}
        record = {
            "model": model,
            "index": i,
            "question": item["question"],
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
            f"{stats.get('tokens_per_sec', 0):5.1f}tok/s {mark}",
            flush=True,
        )

    return summarize(model, records)


def summarize(model: str, records: list) -> dict:
    ok = [r for r in records if not r["error"]]
    times = sorted(r["elapsed_sec"] for r in ok)
    return {
        "model": model,
        "total": len(records),
        "errors": len(records) - len(ok),
        "refused": sum(1 for r in ok if r["refused"]),
        "mean_sec": round(sum(times) / len(times), 2) if times else 0,
        "median_sec": times[len(times) // 2] if times else 0,
        "p90_sec": times[int(len(times) * 0.9)] if times else 0,
        "under_4s": sum(1 for t in times if t <= 4.0),
        "mean_prompt_tokens": round(
            sum(r.get("prompt_tokens", 0) for r in ok) / len(ok)
        ) if ok else 0,
        "mean_output_tokens": round(
            sum(r.get("output_tokens", 0) for r in ok) / len(ok)
        ) if ok else 0,
    }


def unload(model: str):
    """다음 모델을 재기 전에 앞 모델을 메모리에서 내린다.
    두 모델이 같이 올라가 있으면 뒤에 재는 쪽이 스왑에 눌려 불리해진다."""
    import requests

    try:
        requests.post(
            f"{config.OLLAMA_HOST}/api/generate",
            json={"model": model, "keep_alive": 0},
            timeout=30,
        )
    except requests.RequestException:
        pass
    time.sleep(5)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) < 2:
        print("사용법: python3 app/compare_models.py <모델A> <모델B> [질문수]")
        sys.exit(1)

    model_a, model_b = args[0], args[1]
    count = int(args[2]) if len(args) > 2 else 30

    questions = build_questions(count)
    if not questions:
        print("인덱싱된 데이터가 없습니다. 먼저 sync.py를 실행하세요.")
        sys.exit(1)

    print(f"질문 {len(questions)}개로 {model_a} 와 {model_b} 비교")

    summaries = []
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        for model in (model_a, model_b):
            speed = measure_throughput(config.OLLAMA_HOST, model)
            print(f"\n{model} 생성 속도 {speed} tok/s", end="")
            if speed < MIN_THROUGHPUT:
                print(f" — 기준 {MIN_THROUGHPUT} 미만. 응답 시간은 참고용.")
            else:
                print(" — 측정 가능")

            summary = run_model(model, questions, fh)
            summary["throughput"] = speed
            summaries.append(summary)
            unload(model)

    print_comparison(summaries)


def print_comparison(summaries: list):
    print("\n===== 모델 비교 =====")
    header = f"{'항목':<16}" + "".join(f"{s['model']:>14}" for s in summaries)
    print(header)
    rows = [
        ("생성속도 tok/s", "throughput"),
        ("거부 건수", "refused"),
        ("오류 건수", "errors"),
        ("평균 응답 s", "mean_sec"),
        ("중앙값 s", "median_sec"),
        ("p90 s", "p90_sec"),
        ("4초 이내", "under_4s"),
        ("입력 토큰", "mean_prompt_tokens"),
        ("출력 토큰", "mean_output_tokens"),
    ]
    for label, key in rows:
        print(f"{label:<16}" + "".join(f"{s[key]:>14}" for s in summaries))

    a, b = summaries[0], summaries[1]
    print(
        f"\n정확도: 거부 {a['refused']}건 → {b['refused']}건 "
        f"({'악화' if b['refused'] > a['refused'] else '유지/개선'})"
    )
    print(f"상세: {REPORT_PATH}")


if __name__ == "__main__":
    main()
