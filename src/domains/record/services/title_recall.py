"""질문 안에 문서 제목이 그대로 들어있으면 그 문서를 직접 가져온다.

임베딩 유사도는 표면이 비슷한 엉뚱한 문서를 잘 집는다. 실측에서
"티맥스 8주차 언제 만들었어?"가 "너가 랭킹 8등이라고? - YouTube"를,
"웹디자인에서 무슨 작업했어?"가 "진 그레이가 피터에게 무슨 짓을"을 1순위로
가져왔다. 정작 제목이 일치하는 문서는 인덱스에 있는데도 후보에 못 들었다.
"""

import re

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
MIN_PHRASE_CHARS = 3
MAX_PHRASES = 4

# 질문을 이루는 말은 문서를 가리키지 않으므로 후보 구에서 뺀다.
QUESTION_WORDS = {
    "언제", "무슨", "뭐로", "어떤", "관련해서", "내용이", "있었지", "작업했어",
    "만들었어", "요약해줘", "알려줘", "했어", "뭐", "어디", "누가", "왜", "어떻게",
    "그리고", "에서", "관련", "정리해줘", "설명해줘",
}


def candidate_phrases(question: str) -> list:
    """질문에서 문서 제목일 법한 연속된 말을 뽑는다.
    질문어로 끊어 남는 덩어리를 후보로 삼는다."""
    tokens = TOKEN_PATTERN.findall(question)
    phrases, current = [], []

    for token in tokens:
        if token in QUESTION_WORDS:
            if current:
                phrases.append(" ".join(current))
                current = []
            continue
        # "웹디자인에서" 같은 말은 조사만 떼면 제목이 된다.
        for particle in ("에서", "에게", "으로", "에는", "의", "은", "는", "이", "가", "을", "를"):
            if token.endswith(particle) and len(token) - len(particle) >= MIN_PHRASE_CHARS:
                token = token[: -len(particle)]
                break
        current.append(token)
    if current:
        phrases.append(" ".join(current))

    phrases = [p for p in phrases if len(p.replace(" ", "")) >= MIN_PHRASE_CHARS]
    phrases.sort(key=len, reverse=True)
    return phrases[:MAX_PHRASES]


def merge_title_matches(vector_repository, query_embedding, question: str, candidates: list, limit: int) -> list:
    """제목이 질문 속 구와 겹치는 문서를 후보 앞에 세운다."""
    phrases = candidate_phrases(question)
    if not phrases:
        return candidates

    matches = vector_repository.search_by_title_keywords(query_embedding, phrases, limit)
    if not matches:
        return candidates

    seen = {(c.source, c.title) for c in matches}
    return matches + [c for c in candidates if (c.source, c.title) not in seen]
