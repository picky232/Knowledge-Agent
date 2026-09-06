"""날짜 질의에서 그날 일지를 유사도와 무관하게 확보한다.

일지는 하루치를 요약한 문서라 "어제 뭐 했어" 같은 질문의 정답에 가장 가깝다.
그런데 코사인 유사도로만 뽑으면 그날 방문기록 수백 건에 밀려 후보에도 못 든다
(실측: 9/5 일지가 날짜 필터 상위 50 밖). 그래서 따로 집어온다.
"""

JOURNAL_SOURCE = "journal"


def merge_journal_for_date(vector_repository, query_embedding, date_range, candidates: list) -> list:
    """날짜 범위에 해당하는 일지를 후보 맨 앞에 올린다."""
    if not date_range:
        return candidates

    date_from, date_to = date_range
    journals = vector_repository.search_source_within_date(
        query_embedding, JOURNAL_SOURCE, date_from, date_to, top_k=2
    )
    if not journals:
        return candidates

    seen = {(c.source, c.title) for c in journals}
    rest = [c for c in candidates if (c.source, c.title) not in seen]
    return journals + rest
