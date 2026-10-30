"""Turn the model's answer text into structured data for the interface.

No LangChain or OpenAI here: plain functions, easy to test.
- answer_kind():     answered / partial / conflict / not_found
- build_citations(): number every [document title, p. X] and attach a link to that PDF page
"""
import re

# [Refund and Complaint Handling Policy, p. 3]  or  [Returns ... (DEL-RET-004, v3.2), p. 4]
CITATION = re.compile(r"\[([^\[\]]+?),\s*(?:p\.|page)\s*(\d+)\]", re.IGNORECASE)

NOT_FOUND = "i could not find this in the ironstore documents"
PARTIAL_HINTS = re.compile(
    r"\b(?:do(?:es)? not (?:specify|state|give|say|include|list|mention|provide)|not (?:specified|stated))\b",
    re.IGNORECASE,
)

AREA_LABELS = {
    "Customer_support": "Customer support",
    "Deliveries": "Deliveries",
    "Finance": "Finance",
    "HR_policies": "People & HR",
    "IT": "IT & security",
    "Legal_Terms": "Legal",
    "Sales": "Sales",
    "product_catalog": "Product catalogue",
}


def clean_title(raw: str) -> str:
    """'Returns and Reverse Logistics Procedure (DEL-RET-004, v3.2)' -> 'Returns and Reverse Logistics Procedure'"""
    return re.sub(r"\s*\([^()]*\)\s*$", "", raw).strip()


def answer_kind(answer: str) -> str:
    low = answer.strip().lower()
    if low.startswith(NOT_FOUND) or (NOT_FOUND in low and len(low) < 160):
        return "not_found"
    if low.startswith("the documents differ"):
        return "conflict"
    if PARTIAL_HINTS.search(answer):
        return "partial"
    return "answered"


def _find_meta(title: str, metas: list) -> dict | None:
    low = title.lower()
    for m in metas:
        if m["doc_title"].lower() == low:
            return m
    for m in metas:  # the model sometimes shortens or extends the title
        t = m["doc_title"].lower()
        if t in low or low in t:
            return m
    return None


def build_citations(answer: str, metas: list, library: list = ()) -> tuple[list, str]:
    """Number citations in order of first appearance.

    metas: metadata dicts of the chunks the model was given.
    library: one metadata dict per document in the store, used when the model cites a document
             that was not among the retrieved chunks (so its card can still link to the PDF).
    Returns (citations, answer_marked), where answer_marked has every citation replaced by ⟦n⟧
    so the interface can draw a footnote marker in exactly that spot.
    """
    read_pages = {(m["doc_title"].lower(), int(m["page"])) for m in metas}
    citations, index = [], {}

    def replace(match):
        title, page = clean_title(match.group(1)), int(match.group(2))
        meta = _find_meta(title, metas) or _find_meta(title, list(library))
        key = ((meta["doc_title"] if meta else title).lower(), page)
        if key not in index:
            index[key] = len(citations) + 1
            citations.append({
                "n": index[key],
                "title": meta["doc_title"] if meta else title,
                "page": page,
                "url": ("/" + meta["source"].replace("\\", "/") + f"#page={page}") if meta else None,
                "doc_id": meta.get("doc_id") if meta else None,
                "version": meta.get("version") if meta else None,
                "area": AREA_LABELS.get(meta.get("area"), meta.get("area")) if meta else None,
                "last_reviewed": meta.get("last_reviewed") if meta else None,
                "page_was_read": key in read_pages,   # False = the model cited a page it was not given
            })
        return f"⟦{index[key]}⟧"

    answer_marked = CITATION.sub(replace, answer)
    return citations, answer_marked
