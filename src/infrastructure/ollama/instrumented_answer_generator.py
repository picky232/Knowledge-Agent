"""응답 생성기를 감싸 Ollama가 돌려주는 토큰 통계를 함께 기록한다.

응답 시간만 재면 측정 환경에 속는다. 이 프로젝트에서만 세 번 당했다:
다른 작업과 동시에 돌려 790초·4,017초가 찍혔고, 스왑 8.7GB 상태에서 생성
속도가 17 tok/s에서 4.4 tok/s로 떨어져 평균이 23.9초로 나왔다. 그때마다
숫자를 먼저 적고 나중에 원인을 캤다.

입력·출력 토큰 수는 메모리 상태와 무관하므로 검색 품질 변화를 그대로 보여주고,
tok/s는 측정 환경이 쓸 만한지를 그 자리에서 알려준다. 두 지표를 같이 남기면
나쁜 숫자가 스스로를 식별한다.

IAnswerGenerator 구현체라 AskQuestionUseCase에 그대로 끼워 넣을 수 있다.
"""

import requests

from domains.record.repositories.i_answer_generator import IAnswerGenerator
from infrastructure.ollama.ollama_answer_generator import (
    KEEP_ALIVE,
    MAX_ANSWER_TOKENS,
    PROMPT_TEMPLATE,
    _build_context,
)

NANOSECONDS = 1_000_000_000


class InstrumentedAnswerGenerator(IAnswerGenerator):
    """OllamaAnswerGenerator와 같은 프롬프트·옵션으로 생성하되 통계를 보관한다."""

    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model
        self.last_stats = {}

    def generate(self, question: str, context_chunks: list) -> str:
        if not context_chunks:
            self.last_stats = {}
            return "관련 기록을 찾지 못했습니다."

        context = _build_context(context_chunks)
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)

        resp = requests.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "think": False,
                "stream": False,
                "keep_alive": KEEP_ALIVE,
                "options": {"num_predict": MAX_ANSWER_TOKENS},
            },
            timeout=180,
        )
        resp.raise_for_status()
        payload = resp.json()
        self.last_stats = _extract_stats(payload)
        return payload["response"].strip()


def _extract_stats(payload: dict) -> dict:
    eval_count = payload.get("eval_count", 0)
    eval_duration = payload.get("eval_duration", 0)
    prompt_count = payload.get("prompt_eval_count", 0)
    prompt_duration = payload.get("prompt_eval_duration", 0)

    return {
        "prompt_tokens": prompt_count,
        "output_tokens": eval_count,
        "prompt_sec": round(prompt_duration / NANOSECONDS, 2),
        "generate_sec": round(eval_duration / NANOSECONDS, 2),
        "tokens_per_sec": round(eval_count / (eval_duration / NANOSECONDS), 1)
        if eval_duration
        else 0.0,
    }


def measure_throughput(host: str, model: str) -> float:
    """짧은 생성을 한 번 돌려 지금 이 순간의 생성 속도(tok/s)를 잰다.

    측정 전 환경 점검용. vm_stat의 여유 페이지 수는 macOS가 비활성 페이지를
    회수하기 때문에 실제 성능과 잘 안 맞는다. 생성 속도를 직접 재는 편이 정확하다.
    """
    resp = requests.post(
        f"{host.rstrip('/')}/api/generate",
        json={
            "model": model,
            "prompt": "1부터 20까지 세어줘.",
            "think": False,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"num_predict": 60},
        },
        timeout=180,
    )
    resp.raise_for_status()
    return _extract_stats(resp.json())["tokens_per_sec"]
