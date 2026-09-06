import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import container
from domains.record.useCases.build_daily_journal import BuildDailyJournalUseCase
from domains.record.useCases.build_topic_index import BuildTopicIndexUseCase
from domains.record.useCases.index_documents import IndexDocumentsUseCase
from presentation.cli.formatter import format_index_stats


def main():
    vector_repository = container.build_vector_repository()

    use_case = IndexDocumentsUseCase(
        sources=container.build_sources(),
        embedding_service=container.build_embedding_service(),
        vector_repository=vector_repository,
    )
    stats = use_case.run()
    print(format_index_stats(stats))

    journal_use_case = BuildDailyJournalUseCase(
        vector_repository=vector_repository,
        summarizer=container.build_summarizer(),
        journal_writer=container.build_journal_writer(),
    )
    journal_stats = journal_use_case.run()
    print(
        f"활동 일지 갱신: 총 {journal_stats['days']}일 "
        f"(신규 {journal_stats['written']}, 재사용 {journal_stats['reused']})"
    )

    index_use_case = BuildTopicIndexUseCase(
        vector_repository=vector_repository,
        summarizer=container.build_summarizer(),
        index_writer=container.build_index_writer(),
    )
    index_stats = index_use_case.run()
    print(
        f"주제 인덱스 갱신: 총 {index_stats['topics']}개 "
        f"(재요약 {index_stats['summarized']}, 재사용 {index_stats['reused']})"
    )


if __name__ == "__main__":
    main()
