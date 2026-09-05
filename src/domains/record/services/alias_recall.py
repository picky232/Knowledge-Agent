import re

from domains.record.services.term_aliases import expand_terms

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]{2,}")


def alias_keywords_for(question: str) -> list:
    """질문에서 별칭으로 확장된 표기만 추려낸다.

    "유튜브에서 뭐 봤어?" -> ["youtube", "유튜브"] 처럼, 질문에 없던 다른 표기를
    얻었을 때만 값이 생긴다. 확장이 없으면 빈 리스트라 추가 조회를 하지 않는다."""
    tokens = set(TOKEN_PATTERN.findall(question.lower()))
    expanded = expand_terms(tokens)
    return sorted(expanded - tokens)


def merge_alias_matches(vector_repository, query_embedding, question: str, candidates: list, limit: int) -> list:
    """별칭 표기로 제목이 걸리는 청크를 후보군 앞에 덧붙인다.

    임베딩 유사도만으로는 표기가 다른 기록(질문은 한글, 제목은 영문)이
    후보군 밖으로 밀려나므로, 그런 경우에만 제목 검색으로 따로 건져온다."""
    keywords = alias_keywords_for(question)
    if not keywords:
        return candidates

    matches = vector_repository.search_by_title_keywords(query_embedding, keywords, limit)
    if not matches:
        return candidates

    seen = {(c.source, c.title) for c in matches}
    return matches + [c for c in candidates if (c.source, c.title) not in seen]
