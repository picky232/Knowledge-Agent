import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import container
from domains.record.useCases.index_documents import IndexDocumentsUseCase
from presentation.cli.formatter import format_index_stats


def main():
    use_case = IndexDocumentsUseCase(
        sources=container.build_sources(),
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
    )
    stats = use_case.run()
    print(format_index_stats(stats))


if __name__ == "__main__":
    main()
