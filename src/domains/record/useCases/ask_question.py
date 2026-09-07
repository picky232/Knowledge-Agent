from domains.record.entities.record import AnswerResult
from domains.record.services.retrieval_pipeline import CANDIDATE_POOL_SIZE, retrieve


class AskQuestionUseCase:
    def __init__(self, embedding_service, vector_repository, answer_generator):
        self.embedding_service = embedding_service
        self.vector_repository = vector_repository
        self.answer_generator = answer_generator

    def run(self, question: str, top_k: int = 5) -> AnswerResult:
        chunks = retrieve(
            self.vector_repository, self.embedding_service, question, top_k, CANDIDATE_POOL_SIZE
        )
        answer = self.answer_generator.generate(question, chunks)
        return AnswerResult(answer=answer, citations=chunks)
