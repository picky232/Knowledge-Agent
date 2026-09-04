from domains.record.entities.record import AnswerResult
from domains.record.services.keyword_boost import boost_by_keyword_overlap

CANDIDATE_POOL_SIZE = 20


class AskQuestionUseCase:
    def __init__(self, embedding_service, vector_repository, answer_generator):
        self.embedding_service = embedding_service
        self.vector_repository = vector_repository
        self.answer_generator = answer_generator

    def run(self, question: str, top_k: int = 5) -> AnswerResult:
        query_embedding = self.embedding_service.embed([question])[0]
        candidates = self.vector_repository.search(query_embedding, max(top_k, CANDIDATE_POOL_SIZE))
        chunks = boost_by_keyword_overlap(question, candidates, top_k)
        answer = self.answer_generator.generate(question, chunks)
        return AnswerResult(answer=answer, citations=chunks)
