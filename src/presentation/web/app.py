import json
import os
import queue
import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import container
from domains.record.services.retrieval_pipeline import DEFAULT_TOP_K
from domains.record.useCases.ask_question_resumable import AskQuestionResumableUseCase
from infrastructure.chatlog.chat_log_source import append_turn

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# 창을 숨기는 콜백은 GUI 프로세스가 등록한다(웹 브라우저로 열었을 땐 없음).
hide_callback = {"fn": None}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/quick")
def quick():
    return FileResponse(os.path.join(STATIC_DIR, "quick.html"))


@app.get("/api/hide")
def hide():
    fn = hide_callback["fn"]
    if fn:
        fn()
        return {"hidden": True}
    return {"hidden": False}


@app.get("/api/ask-stream")
def ask_stream(question: str):
    use_case = AskQuestionResumableUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=container.build_answer_generator(),
        state_store=container.build_generation_state_store(),
        top_k=DEFAULT_TOP_K,
    )

    def event_gen():
        q = queue.Queue()
        first_token_seen = [False]

        def on_answer(delta: str):
            if not first_token_seen[0]:
                first_token_seen[0] = True
                q.put(("generating", None))
            q.put(("token", delta))

        def worker():
            try:
                q.put(("searching", None))
                # 추론은 끈다. on_thinking을 넘기지 않으므로 추론 토큰은 화면에
                # 닿지도 못하고 버려지는데, 그 사이 사용자는 첫 글자를 기다린다.
                # 답변 자체는 근거 조각을 그대로 요약하는 일이라 추론이 필요 없다.
                result = use_case.run(question, think=False, on_answer=on_answer)
                q.put(("done", result))
            except Exception as e:
                q.put(("error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            kind, payload = q.get()
            if kind in ("searching", "generating"):
                yield f"data: {json.dumps({'type': kind}, ensure_ascii=False)}\n\n"
            elif kind == "token":
                yield f"data: {json.dumps({'type': 'token', 'text': payload}, ensure_ascii=False)}\n\n"
            elif kind == "done":
                citations = [
                    {"source": c.source, "title": c.title, "url": c.url, "updated_at": c.updated_at}
                    for c in payload.citations
                ]
                try:
                    append_turn(container.CHAT_LOG_PATH, question, payload.answer)
                except Exception:
                    pass  # 기록 실패가 답변을 막지는 않게
                yield f"data: {json.dumps({'type': 'done', 'citations': citations}, ensure_ascii=False)}\n\n"
                break
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': payload}, ensure_ascii=False)}\n\n"
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream")
