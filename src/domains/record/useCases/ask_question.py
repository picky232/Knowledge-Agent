from domains.record.entities.record import AnswerResult
from domains.record.services.alias_recall import merge_alias_matches
from domains.record.services.date_intent import detect_date_range
from domains.record.services.journal_recall import merge_journal_for_date
from domains.record.services.source_quota import apply_source_quota
from domains.record.services.keyword_boost import boost_by_keyword_overlap, dedup_by_title, prioritize_episodic_sources

CANDIDATE_POOL_SIZE = 50


class AskQuestionUseCase:
    def __init__(self, embedding_service, vector_repository, answer_generator):
        self.embedding_service = embedding_service
        self.vector_repository = vector_repository
        self.answer_generator = answer_generator

    def run(self, question: str, top_k: int = 5) -> AnswerResult:
        query_embedding = self.embedding_service.embed([question])[0]

        date_range = detect_date_range(question)
        candidates = []
        used_date_filter = False
        if date_range:
            candidates = self.vector_repository.search_within_date(query_embedding, *date_range, CANDIDATE_POOL_SIZE)
            used_date_filter = bool(candidates)
        if not candidates:
            candidates = self.vector_repository.search(query_embedding, max(top_k, CANDIDATE_POOL_SIZE))

        if used_date_filter:
            candidates = prioritize_episodic_sources(candidates)
        candidates = merge_alias_matches(
            self.vector_repository, query_embedding, question, candidates, top_k
        )
        candidates = merge_journal_for_date(self.vector_repository, query_embedding, date_range, candidates)
        candidates = apply_source_quota(candidates)
        candidates = dedup_by_title(candidates)
        chunks = boost_by_keyword_overlap(question, candidates, top_k)
        answer = self.answer_generator.generate(question, chunks)
        return AnswerResult(answer=answer, citations=chunks)
