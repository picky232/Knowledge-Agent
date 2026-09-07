"""질문에 답할 근거 조각을 고르는 한 곳.

이 순서는 원래 AskQuestionUseCase와 AskQuestionResumableUseCase에 똑같이
복사돼 있었고, 한쪽에만 단계가 추가되면서 갈라졌다. 제목으로 찾은 문서를
앞부분으로 바꾸는 단계(promote_document_heads)가 질의 유스케이스에만 들어가는
바람에, 정작 사람이 쓰는 채팅창(웹·GUI·빠른 질문 창은 전부 재개형을 쓴다)에는
그 개선이 닿지 않았다. 두 유스케이스가 같은 함수를 부르면 이런 어긋남이 없다.
"""

from domains.record.services.alias_recall import merge_alias_matches
from domains.record.services.date_intent import detect_date_range
from domains.record.services.head_recall import promote_document_heads
from domains.record.services.journal_recall import merge_journal_for_date
from domains.record.services.keyword_boost import (
    boost_by_keyword_overlap,
    dedup_by_title,
    prioritize_episodic_sources,
)
from domains.record.services.source_quota import apply_source_quota
from domains.record.services.title_recall import merge_title_matches

CANDIDATE_POOL_SIZE = 50


def retrieve(vector_repository, embedding_service, question: str, top_k: int,
             pool_size: int = CANDIDATE_POOL_SIZE) -> list:
    query_embedding = embedding_service.embed([question])[0]

    date_range = detect_date_range(question)
    candidates = []
    used_date_filter = False
    if date_range:
        candidates = vector_repository.search_within_date(query_embedding, *date_range, pool_size)
        used_date_filter = bool(candidates)
    if not candidates:
        candidates = vector_repository.search(query_embedding, max(top_k, pool_size))

    if used_date_filter:
        candidates = prioritize_episodic_sources(candidates)
    candidates = merge_alias_matches(vector_repository, query_embedding, question, candidates, top_k)
    candidates = merge_title_matches(vector_repository, query_embedding, question, candidates, top_k)
    candidates = merge_journal_for_date(vector_repository, query_embedding, date_range, candidates)
    candidates = apply_source_quota(candidates)
    candidates = dedup_by_title(candidates)
    chunks = boost_by_keyword_overlap(question, candidates, top_k)
    # 최종 선정 뒤에 바꾼다 — 후보 전체에 하면 조회가 pool_size번 나가는데,
    # 여기서는 많아야 top_k번이고 결과는 같다.
    return promote_document_heads(vector_repository, question, chunks)
