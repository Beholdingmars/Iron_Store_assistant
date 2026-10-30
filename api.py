"""HTTP API + web interface for the IronStore assistant.  Run:  uvicorn api:app --reload"""
import json
import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import rag

BASE = Path(__file__).parent
logger = logging.getLogger("ironstore")
app = FastAPI(title="IronStore Enterprise AI Assistant")


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


# --- protect the OpenAI key on a public URL: per-visitor and per-day limits ---------------------
PER_MINUTE = int(os.getenv("RATE_PER_MINUTE", "6"))
PER_DAY = int(os.getenv("DAILY_CAP", "300"))
_recent = defaultdict(deque)
_today = {"date": "", "count": 0}


def rate_limit(request: Request):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()
    now, hits = time.time(), _recent[ip]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= PER_MINUTE:
        raise HTTPException(429, "That's a lot of questions in one minute. Wait a moment, then try again.")
    day = time.strftime("%Y-%m-%d")
    if _today["date"] != day:
        _today.update(date=day, count=0)
    if _today["count"] >= PER_DAY:
        raise HTTPException(429, "The assistant has answered its daily limit of questions. Try again tomorrow.")
    hits.append(now)
    _today["count"] += 1


@app.get("/health")
def health():
    return {"status": "ok", **rag.corpus_stats()}


@app.post("/ask", dependencies=[Depends(rate_limit)])
def ask(body: Question):
    """One JSON answer: answer, kind, route, model, citations."""
    return rag.answer_question(body.question.strip())


@app.post("/ask/stream", dependencies=[Depends(rate_limit)])
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
