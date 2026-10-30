"""Core RAG logic of the IronStore assistant (moved from the notebook so the API can use it).

The vector store is built once by the notebook and persisted in ./chroma_db.
"""
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from answer_format import answer_kind, build_citations

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

# --- vector stores (two collections) and retrievers ---------------------------------------------
emb = OpenAIEmbeddings(model="text-embedding-3-small")
internal_db = Chroma(collection_name="internal_docs", persist_directory=str(BASE / "chroma_db"), embedding_function=emb)
catalog_db = Chroma(collection_name="product_catalog", persist_directory=str(BASE / "chroma_db"), embedding_function=emb)

internal_retriever = internal_db.as_retriever(search_kwargs={"k": 6})
# the outdated 2021 catalog is excluded from every search
catalog_retriever = catalog_db.as_retriever(search_kwargs={"k": 4, "filter": {"status": "current"}})

# --- models --------------------------------------------------------------------------------------
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)          # router
strong_llm = ChatOpenAI(model="gpt-4o", temperature=0)        # answers

# --- prompts -------------------------------------------------------------------------------------
router_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Classify a question about IronStore. Reply with exactly one word: "
     "'policy' (internal policies and procedures: HR, finance, IT, legal, sales, support, deliveries, approvals), "
     "'product' (products, prices, availability, SKUs, catalog) or 'both'."),
    ("human", "{question}"),
])
router = router_prompt | llm | StrOutputParser()

prompt_v2 = ChatPromptTemplate.from_messages([
    ("system",
     "You are IronStore's internal assistant. Answer ONLY with the context below, which is grouped by "
     "document: each group starts with '=== DOCUMENT: title (id, version) ===' and every page block starts "
     "with its marker [p. X]. "
     "CITATIONS: cite every claim as [document title, p. X]. Take the title from the group header and the page X "
     "from the marker of the exact block that contains the fact (for example the block with the price or the rule), "
     "not from another block of the same document. Ignore any 'Page N' or 'Section' label written inside the text. "
     "NO ANSWER: only if the documents do not discuss the topic at all, reply exactly: "
     "'I could not find this in the IronStore documents.' "
     "PARTIAL ANSWER: if the documents discuss the topic but do not state the exact value asked for, do NOT "
     "use that sentence. Instead say what the documents state, what is missing, and where they say it can be "
     "found. Example: asked for a limit that a document says is set in each employee's contract, answer that "
     "the documents do not give a single figure and that it is set in the contract, citing the document. "
     "Documents contain a version history: apply the current rules, not older versions listed there. "
     "ANSWER FORMAT: (1) one or two sentences with the answer. "
     "(2) If more than one document addresses the question, go through EVERY document group in the context "
     "that is relevant and add one line each: '- <document title>: <what it says> [title, p. X]'. "
     "(3) If those documents give different rules, thresholds or approvers for the same case, "
     "start the answer with 'The documents differ:' and do not choose one of them."),
    ("human", "Context:\n{context}\n\nQuestion: {question}"),
])
answer_chain = prompt_v2 | strong_llm | StrOutputParser()


def format_docs_grouped(docs):
    groups = defaultdict(list)
    for d in docs:
        m = d.metadata
        groups[(m["doc_title"], m["doc_id"], m["version"])].append(d)
    parts = []
    for (title, doc_id, ver), ds in groups.items():
        v = f", v{ver}" if ver != "n/a" else ""
        parts.append(f"=== DOCUMENT: {title} ({doc_id}{v}) ===")
        for d in sorted(ds, key=lambda x: x.metadata["page"]):
            parts.append(f"[p. {d.metadata['page']}]\n{d.page_content}")
    return "\n\n".join(parts)


# --- the pipeline, step by step ------------------------------------------------------------------
def choose_route(question: str) -> str:
    route = router.invoke({"question": question}).strip().lower()
    return route if route in ("policy", "product", "both") else "both"   # unsure -> search everywhere


def retrieve(question: str, route: str) -> list:
    docs = []
    if route in ("policy", "both"):
        docs += internal_retriever.invoke(question)
    if route in ("product", "both"):
        docs += catalog_retriever.invoke(question)
    return docs


def package(answer: str, route: str, docs: list) -> dict:
    """Everything the interface needs about one finished answer."""
    citations, answer_marked = build_citations(answer, [d.metadata for d in docs], library())
    return {
        "answer": answer,
        "answer_marked": answer_marked,
        "kind": answer_kind(answer),
        "route": route,
        "model": strong_llm.model_name,
        "citations": citations,
        "sources": citations,          # kept for clients of the first API version
    }


def answer_question(question: str) -> dict:
    route = choose_route(question)
    docs = retrieve(question, route)
    answer = answer_chain.invoke({"context": format_docs_grouped(docs), "question": question})
    return package(answer, route, docs)


def stream_answer(question: str):
    """Same pipeline as answer_question, but yields events so the interface can show real progress."""
    yield {"type": "status", "step": "routing"}
    route = choose_route(question)
    yield {"type": "status", "step": "searching", "route": route}
    docs = retrieve(question, route)
    yield {"type": "status", "step": "writing", "documents": len({d.metadata["doc_title"] for d in docs})}
    parts = []
    for chunk in answer_chain.stream({"context": format_docs_grouped(docs), "question": question}):
        parts.append(chunk)
        yield {"type": "delta", "text": chunk}
    yield {"type": "done", **package("".join(parts), route, docs)}


@lru_cache(maxsize=1)
def library() -> list:
    """One metadata dict per current document (to link citations of documents that weren't retrieved)."""
    seen = {}
    for db in (internal_db, catalog_db):
        for m in db._collection.get(include=["metadatas"])["metadatas"]:
            if m.get("status", "current") == "current":
                seen.setdefault(m["doc_title"], m)
    return list(seen.values())


@lru_cache(maxsize=1)
def corpus_stats() -> dict:
    """Counts shown on the home screen (computed once)."""
    internal = internal_db._collection.get(include=["metadatas"])["metadatas"]
    catalog = catalog_db._collection.get(include=["metadatas"])["metadatas"]
    return {
        "internal_chunks": len(internal),
        "catalog_chunks": len(catalog),
        "policies": len({m["source"] for m in internal}),
        "catalogues": len({m["source"] for m in catalog if m.get("status") == "current"}),
        "retired": len({m["source"] for m in catalog if m.get("status") != "current"}),
        "last_reviewed": Counter(m.get("last_reviewed") for m in internal if m.get("last_reviewed")).most_common(1)[0][0],
    }
