import json

import requests

from domains.record.repositories.i_answer_generator import IAnswerGenerator

PROMPT_TEMPLATE = """사용자 본인의 기록을 찾아주는 비서다.
첫 문장에 결론, 다음 줄에 근거. 2~3문장. 인사말·출처표기 없이.
기록에 근거가 없으면 "기록에 없습니다"만 답한다.

[기록]
{context}

질문: {question}
답변:"""

KEEP_ALIVE = "30m"

# 답변은 2~4문장이면 충분한데, 드물게 모델이 멈추지 않고 계속 생성해 응답이
# 수십 초로 늘어나는 경우가 있다. 정상 답변은 이 한도에 걸리지 않는다.
MAX_ANSWER_TOKENS = 200

# 프롬프트 입력 토큰이 응답 시간의 절반 이상을 차지해서(1,123토큰 처리에 6.6초)
# 청크당 본문 길이를 제한한다. 700자에서 350자로 줄여도 답변 품질 차이는 없었다.
MAX_CHUNK_CHARS = 500
JOURNAL_SUMMARY_CHARS = 600

CONTINUATION_SUFFIX = """

[지금까지 생성한 내용]
{partial}

[지시]
위 내용을 처음부터 다시 쓰지 마세요. 끊긴 지점부터 자연스럽게 이어서 계속 작성하세요.
"""


def _build_context(context_chunks: list) -> str:
    return "\n\n".join(
        f"- [{c.source}] {c.title} ({c.updated_at[:10]})\n  {_body_of(c)}"
        for c in context_chunks
    )


def _body_of(chunk) -> str:
    """일지는 '요약 + 항목 나열' 구조라 요약까지만 넣어도 질문에 답할 수 있다.
    전체를 넣으면 프롬프트가 커져 응답이 두 배 이상 느려진다."""
    text = chunk.content
    if chunk.source == "journal":
        head = text.split("\n## ", 1)[0]
        return head[:JOURNAL_SUMMARY_CHARS]
    return text[:MAX_CHUNK_CHARS]


class OllamaAnswerGenerator(IAnswerGenerator):
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def generate(self, question: str, context_chunks: list) -> str:
        if not context_chunks:
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
        return resp.json()["response"].strip()

    def generate_stream(
        self,
        question: str,
        context_chunks: list,
        think: bool = True,
        resume_thinking: str = "",
        resume_answer: str = "",
        on_thinking=None,
        on_answer=None,
    ):
        """스트리밍 생성. 중단 후 재호출 시 resume_thinking/resume_answer로 이어서 생성.

        네트워크 끊김/타임아웃/KeyboardInterrupt는 호출자가 처리 —
        이 메서드는 끊긴 지점까지의 (thinking_text, answer_text)를 예외로도 잃지 않도록
        on_thinking/on_answer 콜백으로 토큰 단위로 즉시 전달한다 (호출자가 매 토큰마다 영속화 가능).
        """
        context = _build_context(context_chunks) if context_chunks else ""
        prompt = PROMPT_TEMPLATE.format(context=context, question=question)

        if resume_thinking or resume_answer:
            partial = (resume_thinking + "\n" + resume_answer).strip()
            prompt += CONTINUATION_SUFFIX.format(partial=partial)

        thinking_text = resume_thinking
        answer_text = resume_answer

        with requests.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "think": think,
                "stream": True,
                "keep_alive": KEEP_ALIVE,
                "options": {"num_predict": MAX_ANSWER_TOKENS},
            },
            timeout=180,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)

                thinking_delta = chunk.get("thinking") or ""
                if thinking_delta:
                    thinking_text += thinking_delta
                    if on_thinking:
                        on_thinking(thinking_delta)

                answer_delta = chunk.get("response") or ""
                if answer_delta:
                    answer_text += answer_delta
                    if on_answer:
                        on_answer(answer_delta)

                if chunk.get("done"):
                    break

        return thinking_text, answer_text.strip()
