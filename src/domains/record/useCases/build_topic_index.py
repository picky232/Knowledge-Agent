class BuildTopicIndexUseCase:
    """인덱싱된 청크를 프로젝트/문서 단위로 묶어 요약하고 md 인덱스로 남긴다.
    내용이 그대로인 주제는 재요약하지 않고 기존 요약을 재사용한다(증분 빌드)."""

    def __init__(self, vector_repository, summarizer, index_writer, max_content_chars: int = 4000):
        self.vector_repository = vector_repository
        self.summarizer = summarizer
        self.index_writer = index_writer
        self.max_content_chars = max_content_chars

    def run(self) -> dict:
        projects = self.vector_repository.list_projects()
        entries = []
        summarized, reused = 0, 0

        for source, project, chunk_count, max_updated_at in projects:
            existing_updated_at = self.index_writer.read_topic_updated_at(source, project)

            if existing_updated_at == max_updated_at:
                summary = self.index_writer.read_topic_summary(source, project)
                reused += 1
            else:
                content = self.vector_repository.get_project_content(source, project, self.max_content_chars)
                summary = self.summarizer.summarize(project, content)
                self.index_writer.write_topic(source, project, summary, chunk_count, max_updated_at)
                summarized += 1

            entries.append({
                "source": source, "project": project, "chunk_count": chunk_count,
                "updated_at": max_updated_at, "summary": summary,
            })

        self.index_writer.write_root_index(entries)
        return {"topics": len(entries), "summarized": summarized, "reused": reused}
