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

# 조사를 뗀 뒤 남아야 하는 최소 길이. 구 전체의 최소 길이(MIN_PHRASE_CHARS)와는
# 다른 기준이다. 한국어 두 음절 명사가 흔해서 3을 요구하면 실제 제목을 놓친다:
# "자료에서"의 "에서"를 못 떼 "취업 지원 증빙 자료"를, "22에서"를 못 떼 "7/22"를
# 찾지 못했다. 그렇다고 가드를 없애면 조사가 아닌 끝음절까지 잘려나간다
# ("의"가 조사 목록에 있어서 "회의"가 "회"가 된다).
MIN_STEM_CHARS = 2

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
            if token.endswith(particle) and len(token) - len(particle) >= MIN_STEM_CHARS:
                token = token[: -len(particle)]
                break
        current.append(token)
    if current:
        phrases.append(" ".join(current))

    phrases = [p for p in phrases if len(p.replace(" ", "")) >= MIN_PHRASE_CHARS]
    phrases.sort(key=len, reverse=True)
    return phrases[:MAX_PHRASES]


# 제목 후보를 넉넉히 받아 밀착도로 다시 세운 뒤 잘라낸다. 유사도로만 잘라내면
# 정작 제목이 똑같은 문서가 먼저 떨어져 나간다.
MATCH_FETCH_FACTOR = 4

NON_TOKEN = re.compile(r"[^0-9A-Za-z가-힣]+")


def _normalize(text: str) -> str:
    return NON_TOKEN.sub("", text.lower())


def _tightness(title: str, phrases: list) -> float:
    """구가 제목을 얼마나 덮는지. 제목과 구가 같으면 1.0에 가깝다.

    제목 검색은 구 안의 공백을 와일드카드로 바꿔 넓게 훑기 때문에, "7 22"가
    "7/22"뿐 아니라 "(78) ...육룡이 나르샤..." 같은 긴 제목까지 끌어온다.
    그 뒤 임베딩 유사도로 고르면 짧은 제목이 진다 — nomic-embed-text가 짧은
    텍스트에 낮은 점수를 주기 때문이다. 실제로 "7/22에서 무슨 작업했어?"가
    유튜브 영상 제목을 1순위로 가져왔다. 덮는 비율로 세우면 이 역전이 사라진다.
    """
    normalized_title = _normalize(title)
    if not normalized_title:
        return 0.0
    best = 0
    for phrase in phrases:
        normalized = _normalize(phrase)
        if normalized and normalized in normalized_title:
            best = max(best, len(normalized))
    return best / len(normalized_title)


def merge_title_matches(vector_repository, query_embedding, question: str, candidates: list, limit: int) -> list:
    """제목이 질문 속 구와 겹치는 문서를 후보 앞에 세운다."""
    phrases = candidate_phrases(question)
    if not phrases:
        return candidates

    matches = vector_repository.search_by_title_keywords(
        query_embedding, phrases, limit * MATCH_FETCH_FACTOR
    )
    if not matches:
        return candidates

    matches.sort(key=lambda c: _tightness(c.title, phrases), reverse=True)
    matches = matches[:limit]

    seen = {(c.source, c.title) for c in matches}
    return matches + [c for c in candidates if (c.source, c.title) not in seen]
