"""질문에 쓰는 한글 표기와 기록에 남는 영문 표기를 이어주는 별칭 사전.

임베딩만으로는 "유튜브"와 "YouTube"가 서로 멀어서(실측 결과 200위 밖)
질문 키워드가 제목에 있어도 검색에서 밀린다. 자주 쓰는 서비스·도구 이름만
양방향으로 넓혀주면 재작성 없이 이 간극을 메울 수 있다.
"""

ALIAS_GROUPS = [
    {"유튜브", "youtube"},
    {"깃허브", "github"},
    {"노션", "notion"},
    {"구글", "google"},
    {"네이버", "naver"},
    {"인스타", "인스타그램", "instagram"},
    {"카톡", "카카오톡", "kakaotalk"},
    {"크롬", "chrome"},
    {"사파리", "safari"},
    {"터미널", "terminal"},
    {"디스코드", "discord"},
    {"슬랙", "slack"},
    {"피그마", "figma"},
    {"블로그", "blog", "tistory", "티스토리"},
    {"백준", "boj", "baekjoon"},
    {"챗지피티", "챗gpt", "chatgpt"},
    {"클로드", "claude"},
    {"파이썬", "python"},
    {"자바스크립트", "javascript"},
    {"리액트", "react"},
]

_ALIAS_MAP = {}
for group in ALIAS_GROUPS:
    for term in group:
        _ALIAS_MAP.setdefault(term, set()).update(group)


def expand_terms(tokens: set) -> set:
    """토큰 집합에 알려진 별칭을 더해서 돌려준다.

    한국어는 "유튜브에서"처럼 조사가 붙어 한 토큰이 되므로, 정확히 일치하는
    경우뿐 아니라 별칭으로 시작하는 토큰도 같은 그룹으로 본다."""
    expanded = set(tokens)
    for token in tokens:
        if token in _ALIAS_MAP:
            expanded.update(_ALIAS_MAP[token])
            continue
        for term, group in _ALIAS_MAP.items():
            if len(term) >= 2 and token.startswith(term):
                expanded.update(group)
                break
    return expanded
