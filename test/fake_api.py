"""Test double of api.py: same endpoints and events, canned answers, no OpenAI and no Chroma.

Run from the project folder:  uvicorn test.fake_api:app --port 8765
"""
import json
import sys
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from answer_format import answer_kind, build_citations  # noqa: E402

DOCS = ROOT / "documents" if (ROOT / "documents").exists() else Path("/tmp/docs_x/documents")
SPEED = float(__import__("os").environ.get("FAKE_SPEED", "1"))
app = FastAPI()


def meta(title, page, path, doc_id, version, area):
    return {"doc_title": title, "page": page, "source": f"documents/{path}", "doc_id": doc_id,
            "version": version, "area": area, "last_reviewed": "August 2026"}


RET = meta("Returns and Reverse Logistics Procedure", 4, "internal_docs_by_area/Deliveries/IronStore_Returns_and_Reverse_Logistics_Procedure.pdf", "DEL-RET-004", "3.2", "Deliveries")
REF = meta("Refund and Complaint Handling Policy", 3, "internal_docs_by_area/Customer_support/IronStore_Refund_and_Complaint_Handling_Policy.pdf", "CS-POL-014", "3.2", "Customer_support")
ESC = meta("Customer Support Escalation Procedures", 4, "internal_docs_by_area/Customer_support/IronStore_Customer_Support_Escalation_Procedures.pdf", "CS-POL-014", "3.2", "Customer_support")
KET = meta("Product Catalog - Home Appliances", 21, "product_catalog/IronStore_Product_Catalog_Home_Appliances.pdf", "IS-HAP-2026.08", "n/a", "product_catalog")
LEAVE = meta("Leave and Absence Policy", 2, "internal_docs_by_area/HR_policies/IronStore_Leave_and_Absence_Policy.pdf", "HR-POL-014", "3.0", "HR_policies")

SCENARIOS = {
    "refund": ("policy", [RET, REF, ESC],
        "The documents differ:\n\n"
        "- Returns and Reverse Logistics Procedure: A refund above €1,000 requires approval from both the Deliveries Manager and Finance Operations [Returns and Reverse Logistics Procedure (DEL-RET-004, v3.2), p. 4].\n"
        "- Refund and Complaint Handling Policy: A refund above €500 requires approval from the Customer Operations Manager and Finance Operations, but it does not specifically mention amounts above €1,000 [Refund and Complaint Handling Policy, p. 3].\n"
        "- Customer Support Escalation Procedures: Amounts above €1,000 require Payments Operations approval and Finance notification [Customer Support Escalation Procedures, p. 4]."),
    "kettle": ("product", [KET],
        "The Veltro VKT-1800 glass kettle costs €59.00 and is in stock [Product Catalog - Home Appliances, p. 21]."),
    "leave": ("policy", [LEAVE],
        "The documents do not specify a fixed number of annual leave days. Your entitlement is shown in your PeopleHub profile and employment contract, and it can vary by country, working pattern, length of service and local agreements [Leave and Absence Policy, p. 2].\n\n"
        "Requests longer than five working days must be made at least 20 calendar days in advance [Leave and Absence Policy, p. 2]."),
    "crypto": ("policy", [], "I could not find this in the IronStore documents."),
}


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=500)


@app.get("/health")
def health():
    return {"status": "ok", "internal_chunks": 341, "catalog_chunks": 2229, "policies": 20,
            "catalogues": 62, "retired": 1, "last_reviewed": "August 2026"}


@app.post("/ask/stream")
def ask_stream(body: Question):
    q = body.question.lower()
    key = next((k for k in SCENARIOS if k in q), None)
    if "days" in q and "leave" in q:
        key = "leave"

    def events():
        yield json.dumps({"type": "status", "step": "routing"}) + "\n"
        time.sleep(0.6 * SPEED)
        if "explode" in q:
            yield json.dumps({"type": "error", "message": "The assistant stopped before finishing this answer."}) + "\n"
            return
        route, metas, answer = SCENARIOS.get(key, SCENARIOS["kettle"])
        yield json.dumps({"type": "status", "step": "searching", "route": route}) + "\n"
        time.sleep(0.7 * SPEED)
        yield json.dumps({"type": "status", "step": "writing", "documents": len({m["doc_title"] for m in metas})}) + "\n"
        time.sleep(0.5 * SPEED)
        words = answer.split(" ")
        for i, w in enumerate(words):
            yield json.dumps({"type": "delta", "text": w + ("" if i == len(words) - 1 else " ")}, ensure_ascii=False) + "\n"
            time.sleep(0.03 * SPEED)
        citations, marked = build_citations(answer, metas)
        yield json.dumps({"type": "done", "answer": answer, "answer_marked": marked, "kind": answer_kind(answer),
                          "route": route, "model": "gpt-4o", "citations": citations, "sources": citations},
                         ensure_ascii=False) + "\n"
    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/documents", StaticFiles(directory=DOCS), name="documents")
