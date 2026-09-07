import json

import requests

from domains.record.repositories.i_answer_generator import IAnswerGenerator

# 형식 지시와 예시는 작은 모델을 위한 것이다. exaone3.5와 gemma3는 불릿과 굵은
# 글씨로 답을 늘어놓아 2~3문장을 넘겼고, 답이 길어진 만큼 완성도 늦어졌다.
# "목록·굵은 글씨 없이 줄글로"는 작은 모델을 위한 것이다. exaone3.5와 gemma3는
# 불릿과 굵은 글씨로 답을 늘어놓아 2~3문장을 넘겼고, 답이 길어진 만큼 완성도 늦어졌다.
# qwen3:8b는 이 지시가 없어도 줄글로 답한다.
#
# 예시 답변을 한 줄 넣어보기도 했다. 처음엔 마크다운이 열두 건 중 일곱 건에서
# 0/5로 사라져 효과가 있는 줄 알았는데, 예시로 고른 문장이 하필 시험 문항 중
# 하나여서 모델이 기록을 읽는 대신 예시를 베껴 쓴 것이었다. 인덱스에 없는
# 문장으로 예시를 바꾸자 마크다운이 그대로 돌아왔다. 토큰만 30개 더 쓰므로 뺐다.
PROMPT_TEMPLATE = """사용자 본인의 기록을 찾아주는 비서다.
첫 문장에 결론, 다음 줄에 근거. 2~3문장.
목록·굵은 글씨·인사말·출처표기 없이 줄글로.
기록에 근거가 없으면 "기록에 없습니다"만 답한다.

[기록]
{context}

질문: {question}
답변:"""

KEEP_ALIVE = "30m"

# 모델이 멈추지 않고 계속 생성해 응답이 수십 초로 늘어나는 것을 막는 한도다.
#
# 200으로 두었더니 exaone3.5는 서른 문항 중 여덟 건이 여기 걸려 단어 중간에서
# 끊겼다("...week2_issues_complete." 하고 끝나는 식이다). 결론은 첫 문장에 이미
# 나와 있으니 내용이 사라지는 건 아니지만 화면에서 망가져 보인다. qwen3:8b는
# 평균 51토큰이라 200이든 320이든 걸리지 않으므로, 한도를 올려도 잃는 게 없다.
#
# 이 값은 첫 글자가 뜨는 시간과는 무관하다 — 그건 프롬프트를 읽는 시간이고,
# 여기서 정하는 건 답이 다 나오기까지의 길이다.
MAX_ANSWER_TOKENS = 320

# 프롬프트 입력 토큰이 응답 시간의 절반 이상을 차지해서(1,123토큰 처리에 6.6초)
# 청크당 본문 길이를 제한한다. 700자에서 350자로 줄여도 답변 품질 차이는 없었다.
# 청크는 인덱싱 단계에서 이미 700자로 나뉘어 있다. 여기서 더 자르면 문서 끝이
# 잘려나가 답을 못 하게 된다(500자로 자르자 노션 문서 질문 31건이 실패했다).
MAX_CHUNK_CHARS = 700
JOURNAL_SUMMARY_CHARS = 600

CONTINUATION_SUFFIX = """

[지금까지 생성한 내용]
{partial}

[지시]
위 내용을 처음부터 다시 쓰지 마세요. 끊긴 지점부터 자연스럽게 이어서 계속 작성하세요.
"""


def _build_context(context_chunks: list) -> str:
    """날짜에 이름을 붙여 적는다.

    예전에는 `- [notion] 7일차 (2026-08-30)`처럼 괄호에만 넣었다. qwen3:8b는
    그 괄호를 작성일로 읽었지만, exaone3.5와 gemma3는 "7일차 언제 만들었어?"에
    둘 다 "기록에 없습니다"라고 답했다. gemma3는 없다고 해놓고 곧바로 그 날짜를
    나열하기까지 했다. 괄호 안의 숫자가 무엇인지 말해주지 않은 쪽 문제였다.
    """
    return "\n\n".join(
        f"- {c.title} | 기록일 {c.updated_at[:10]} | 출처 {c.source}\n  {_body_of(c)}"
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
