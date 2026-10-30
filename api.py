"""HTTP API + web interface for the IronStore assistant.  Run:  uvicorn api:app --reload"""
import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import rag

BASE = Path(__file__).parent
logger = logging.getLogger("ironstore")
app = FastAPI(title="IronStore Enterprise AI Assistant")


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/health")
def health():
    return {"status": "ok", **rag.corpus_stats()}


@app.post("/ask")
def ask(body: Question):
    """One JSON answer: answer, kind, route, model, citations."""
    return rag.answer_question(body.question.strip())


@app.post("/ask/stream")
def ask_stream(body: Question):
    """Same answer as /ask, sent as NDJSON events: status -> delta (text pieces) -> done | error."""
    def events():
        try:
            for event in rag.stream_answer(body.question.strip()):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception:
            logger.exception("Answer failed")
            yield json.dumps({"type": "error",
                              "message": "The assistant stopped before finishing this answer."}) + "\n"
    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE / "static" / "index.html")


app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")          # fonts
app.mount("/documents", StaticFiles(directory=BASE / "documents"), name="documents")  # source PDFs for citations
