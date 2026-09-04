import sys
import os
import sqlite3
import time
import json
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, container
from domains.record.useCases.ask_question import AskQuestionUseCase

QUESTION_TEMPLATES = [
    "{title} 언제 만들었어?",
    "{title} 뭐로 구현했어?",
    "{title} 요약해줘",
    "{title}에서 무슨 작업했어?",
    "{title} 관련해서 어떤 내용이 있었지?",
]

REPORT_PATH = os.path.join(config.BASE_DIR, "data", "benchmark_report.jsonl")


def build_questions(n: int) -> list:
    conn = sqlite3.connect(config.DB_PATH)
    rows = conn.execute("SELECT DISTINCT source, title FROM chunks").fetchall()
    conn.close()

    if not rows:
        return []

    random.seed(42)
    random.shuffle(rows)

    questions = []
    i = 0
    while len(questions) < n and rows:
        source, title = rows[i % len(rows)]
        template = QUESTION_TEMPLATES[i % len(QUESTION_TEMPLATES)]
        questions.append({"source": source, "title": title, "question": template.format(title=title)})
        i += 1
    return questions[:n]


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    questions = build_questions(n)
    if not questions:
        print("인덱싱된 데이터가 없습니다. 먼저 sync.py를 실행하세요.")
        sys.exit(1)

    use_case = AskQuestionUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=container.build_answer_generator(),
    )

    results = []
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        for i, q in enumerate(questions, 1):
            start = time.time()
            error = None
            answer = ""
            citation_count = 0
            try:
                result = use_case.run(q["question"])
                answer = result.answer
                citation_count = len(result.citations)
            except Exception as e:
                error = str(e)
            elapsed = round(time.time() - start, 2)

            record = {
                "index": i, "source": q["source"], "title": q["title"],
                "question": q["question"], "answer": answer,
                "citation_count": citation_count, "elapsed_sec": elapsed, "error": error,
            }
            results.append(record)
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()

            status = "실패" if error else "성공"
            print(f"[{i}/{len(questions)}] {status} ({elapsed}s) {q['question']}")

    ok = [r for r in results if not r["error"]]
    no_citation = [r for r in ok if r["citation_count"] == 0]
    avg_time = round(sum(r["elapsed_sec"] for r in results) / len(results), 2) if results else 0

    print("\n===== 벤치마크 요약 =====")
    print(f"총 질문: {len(results)}")
    print(f"성공: {len(ok)} / 실패: {len(results) - len(ok)}")
    print(f"출처 없이 답한 건수: {len(no_citation)}")
    print(f"평균 응답 시간: {avg_time}s")
    print(f"상세 리포트: {REPORT_PATH}")


if __name__ == "__main__":
    main()
