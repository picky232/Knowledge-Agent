"""파인튜닝 학습셋 생성기.

이 프로젝트가 실제로 하는 일(내 기록을 검색해서 답하기)과 같은 형태로 예시를 만든다.
질문과 검색 결과는 실제 인덱스에서 가져오고, 정답 답변만 원하는 규범에 맞춰 채운다.
"""

import sys
import os
import json
import random
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, container
from domains.record.services.keyword_boost import boost_by_keyword_overlap, dedup_by_title
from infrastructure.ollama.ollama_answer_generator import PROMPT_TEMPLATE, _build_context

QUESTION_TEMPLATES = [
    "{title} 뭐로 만들었어?",
    "{title} 언제 작업했어?",
    "{title} 요약해줘",
    "{title}에서 무슨 작업했어?",
    "{title} 관련해서 뭐 있었지?",
]

OUT_DIR = os.path.join(config.BASE_DIR, "data", "finetune")


def sample_questions(limit: int) -> list:
    conn = sqlite3.connect(config.DB_PATH)
    rows = conn.execute(
        "SELECT DISTINCT source, title FROM chunks WHERE length(title) BETWEEN 4 AND 40"
    ).fetchall()
    conn.close()

    random.seed(7)
    random.shuffle(rows)

    questions = []
    for i, (source, title) in enumerate(rows):
        if len(questions) >= limit:
            break
        template = QUESTION_TEMPLATES[i % len(QUESTION_TEMPLATES)]
        questions.append(template.format(title=title))
    return questions


def build_examples(questions: list) -> list:
    """각 질문에 대해 실제 검색을 수행하고, 학습에 쓸 프롬프트를 조립한다.
    답변(assistant)은 비워두고 반환 — 그 자리는 더 좋은 모델이 채운다."""
    embedding_service = container.build_embedding_service()
    vector_repository = container.build_vector_repository()

    examples = []
    for question in questions:
        query_embedding = embedding_service.embed([question])[0]
        candidates = vector_repository.search(query_embedding, 50)
        candidates = dedup_by_title(candidates)
        chunks = boost_by_keyword_overlap(question, candidates, 5)
        if not chunks:
            continue
        prompt = PROMPT_TEMPLATE.format(context=_build_context(chunks), question=question)
        examples.append({"question": question, "prompt": prompt})
    return examples


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    os.makedirs(OUT_DIR, exist_ok=True)

    questions = sample_questions(count)
    examples = build_examples(questions)

    path = os.path.join(OUT_DIR, "prompts.jsonl")
    with open(path, "w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"{len(examples)}개 생성 → {path}")


if __name__ == "__main__":
    main()
