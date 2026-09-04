from dataclasses import dataclass, field


@dataclass
class GenerationState:
    key: str
    question: str
    stage: str  # "thinking" | "answering" | "done"
    thinking_text: str = ""
    answer_text: str = ""
    citations: list = field(default_factory=list)  # [{source, project, title, url, created_at, updated_at}]
    done: bool = False
    updated_at: str = ""
