def format_answer(result) -> str:
    lines = [result.answer, ""]
    if result.citations:
        lines.append("출처:")
        seen = set()
        for c in result.citations:
            key = (c.source, c.title, c.url)
            if key in seen:
                continue
            seen.add(key)
            date = c.updated_at[:10] if c.updated_at else "?"
            lines.append(f"  - [{c.source}] {c.title} ({date}) {c.url}")
    return "\n".join(lines)


def format_index_stats(stats: dict) -> str:
    lines = ["인덱싱 완료:"]
    for source_name, s in stats.items():
        if "error" in s:
            lines.append(f"  - {source_name}: 실패 ({s['error']})")
            continue
        line = f"  - {source_name}: 문서 {s['documents']}건, 청크 {s['chunks']}건"
        if s.get("failed_documents"):
            line += f" (실패 {s['failed_documents']}건)"
        lines.append(line)
    return "\n".join(lines)
