import json

import requests

from domains.record.repositories.i_answer_generator import IAnswerGenerator

PROMPT_TEMPLATE = """당신은 사용자 본인의 기록(대화, 노션, GitHub, 브라우저 방문기록, 앱·파일 사용기록)을
찾아주는 개인 비서입니다. 아래 자료는 사용자가 실제로 남긴 기록입니다.

[사용자의 기록]
{context}

[질문]
{question}

[답변 규칙]
- 첫 문장에 결론부터 말하세요. 서론이나 "알겠습니다" 같은 인사말 없이 바로 답합니다.
- 그다음 줄에 근거가 되는 구체적 내용(무엇을, 언제, 어떻게)을 덧붙이세요.
- 전체 2~4문장. 대화하듯 자연스러운 한국어로 씁니다.
- 출처 표기(`[notion/...]` 같은 대괄호 표기나 "~자료에서 확인할 수 있습니다" 같은 문장)를 쓰지 마세요.
  출처는 화면에 따로 표시되므로 답변 본문에는 넣지 않습니다.
- 기록에 없으면 첫 문장에서 바로 "기록에 없습니다"라고 자르세요. 추측하거나 지어내지 마세요.
"""

KEEP_ALIVE = "30m"

CONTINUATION_SUFFIX = """

[지금까지 생성한 내용]
{partial}

[지시]
위 내용을 처음부터 다시 쓰지 마세요. 끊긴 지점부터 자연스럽게 이어서 계속 작성하세요.
"""


def _build_context(context_chunks: list) -> str:
    return "\n\n".join(
        f"- [{c.source}/{c.project}] {c.title} ({c.updated_at})\n  {c.content}"
        for c in context_chunks
    )


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
