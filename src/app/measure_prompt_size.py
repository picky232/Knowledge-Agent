"""근거 조각 수를 바꿔가며 프롬프트가 몇 토큰이 되는지 잰다.

첫 글자까지 걸리는 시간은 거의 전부 프롬프트를 읽는 시간이다. 생성 속도가
10.9 tok/s에서 51.1 tok/s로 다섯 배 빨라져도 첫 글자는 4~6초에서 꿈쩍하지
않았다. 그러니 체감 지연을 줄이는 길은 프롬프트를 짧게 만드는 것뿐이다.

답을 만들지 않고 한 토큰만 요청하면 Ollama가 `prompt_eval_count`를 돌려주므로,
저전력 상태에서도 몇 초 만에 조각 수별 토큰 수를 정확히 비교할 수 있다.

사용법:
    python3 app/measure_prompt_size.py [질문수] [조각수,조각수,...] [--model 이름]

토크나이저가 달라도 조각 수에 따른 감소율은 거의 같으므로, 느린 환경에서는
작은 모델로 재는 편이 빠르다.
"""

import os
import statistics
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config, container
from app.run_benchmark import build_questions
from domains.record.services.retrieval_pipeline import CANDIDATE_POOL_SIZE, retrieve
from infrastructure.ollama.ollama_answer_generator import PROMPT_TEMPLATE, _build_context


def prompt_tokens(model: str, prompt: str) -> int:
    """한 토큰만 만들게 해서 프롬프트 토큰 수만 받아온다."""
    resp = requests.post(
        f"{config.OLLAMA_HOST}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "think": False,
            "stream": False,
            "keep_alive": "30m",
            "options": {"num_predict": 1},
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json().get("prompt_eval_count", 0)


def main():
    model = config.ANSWER_MODEL
    if "--model" in sys.argv:
        index = sys.argv.index("--model")
        if index + 1 < len(sys.argv):
            model = sys.argv[index + 1]

    skip = {"--model", model}
    args = [a for a in sys.argv[1:] if not a.startswith("-") and a not in skip]
    count = int(args[0]) if args else 12
    sizes = [int(s) for s in args[1].split(",")] if len(args) > 1 else [5, 4, 3, 2]

    questions = build_questions(count)
    if not questions:
        print("인덱싱된 데이터가 없습니다. 먼저 sync.py를 실행하세요.")
        sys.exit(1)

    embedding_service = container.build_embedding_service()
    vector_repository = container.build_vector_repository()

    print(f"{model} 기준, 질문 {len(questions)}개\n")
    results = {}
    for size in sizes:
        counts = []
        for item in questions:
            chunks = retrieve(
                vector_repository, embedding_service, item["question"], size, CANDIDATE_POOL_SIZE
            )
            prompt = PROMPT_TEMPLATE.format(
                context=_build_context(chunks), question=item["question"]
            )
            counts.append(prompt_tokens(model, prompt))
        results[size] = counts
        print(
            f"근거 {size}개: 평균 {statistics.mean(counts):6.0f}토큰  "
            f"중앙값 {statistics.median(counts):6.0f}  최대 {max(counts):5d}"
        )

    base = statistics.mean(results[sizes[0]])
    print()
    for size in sizes[1:]:
        mean = statistics.mean(results[size])
        print(f"근거 {sizes[0]}개 대비 {size}개: {100 * (1 - mean / base):.0f}% 감소")


if __name__ == "__main__":
    main()
