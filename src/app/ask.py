import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import container
from domains.record.useCases.ask_question import AskQuestionUseCase
from presentation.cli.formatter import format_answer


def main():
    if len(sys.argv) < 2:
        print("사용법: python ask.py \"질문\"")
        sys.exit(1)
    question = " ".join(sys.argv[1:])

    use_case = AskQuestionUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=container.build_answer_generator(),
    )
    result = use_case.run(question)
    print(format_answer(result))


if __name__ == "__main__":
    main()
