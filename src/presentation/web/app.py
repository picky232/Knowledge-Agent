import json
import os
import queue
import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app import container
from domains.record.useCases.ask_question_resumable import AskQuestionResumableUseCase

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/ask-stream")
def ask_stream(question: str):
    use_case = AskQuestionResumableUseCase(
        embedding_service=container.build_embedding_service(),
        vector_repository=container.build_vector_repository(),
        answer_generator=container.build_answer_generator(),
        state_store=container.build_generation_state_store(),
    )

    def event_gen():
        q = queue.Queue()

        def on_answer(delta: str):
            q.put(("token", delta))

        def worker():
            try:
                result = use_case.run(question, think=True, on_answer=on_answer)
                q.put(("done", result))
            except Exception as e:
                q.put(("error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

        while True:
            kind, payload = q.get()
            if kind == "token":
                yield f"data: {json.dumps({'type': 'token', 'text': payload}, ensure_ascii=False)}\n\n"
            elif kind == "done":
                citations = [
                    {"source": c.source, "title": c.title, "url": c.url, "updated_at": c.updated_at}
                    for c in payload.citations
                ]
                yield f"data: {json.dumps({'type': 'done', 'citations': citations}, ensure_ascii=False)}\n\n"
                break
            else:
                yield f"data: {json.dumps({'type': 'error', 'message': payload}, ensure_ascii=False)}\n\n"
                break

    return StreamingResponse(event_gen(), media_type="text/event-stream")
