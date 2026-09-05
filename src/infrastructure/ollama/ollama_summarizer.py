import requests

from domains.record.repositories.i_document_summarizer import IDocumentSummarizer

PROMPT_TEMPLATE = """다음은 "{title}" 관련 기록입니다. 이 내용을 한국어로 2~4문장으로 요약하세요.
무엇에 관한 것인지, 언제(날짜가 있으면) 어떤 작업/내용이었는지 중심으로 요약하고,
자료에 없는 내용은 추측하지 마세요.

[내용]
{content}

[요약]
"""


class OllamaSummarizer(IDocumentSummarizer):
    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def summarize(self, title: str, content: str) -> str:
        if not content.strip():
            return "(내용 없음)"

        prompt = PROMPT_TEMPLATE.format(title=title, content=content)
        resp = requests.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "think": False,
                "stream": False,
                "keep_alive": "30m",
            },
            timeout=120,
        )
        resp.raise_for_status()
        text = resp.json()["response"].strip()

        # 내용이 짧으면 모델이 프롬프트 틀([내용]/[요약])까지 그대로 따라 쓸 때가 있음 —
        # 마지막 [요약] 이후만 실제 답변으로 취급
        marker = "[요약]"
        if marker in text:
            text = text.rsplit(marker, 1)[-1].strip()

        return text
