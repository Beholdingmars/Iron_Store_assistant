"""Build the vector store (./chroma_db) from the PDFs in ./documents.

Same steps as the notebook (cells 7, 8 and 12), as a script so a server can rebuild the index:
    python ingest.py
Cost: ~2,600 chunks with text-embedding-3-small, about $0.02 per run.
"""
import re
import shutil
from pathlib import Path

from dotenv import load_dotenv
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / ".env")
INTERNAL = BASE / "documents" / "internal_docs_by_area"
CATALOG = BASE / "documents" / "product_catalog"
DB = BASE / "chroma_db"


def header_field(text, label):
    m = re.search(rf"{label}:\s*([^\n|]+)", text)
    return m.group(1).strip() if m else None


def last_reviewed_of(text):
    m = re.search(r"Last reviewed(?: in)?:?\s*([A-Za-z]+ \d{4})", text)
    return m.group(1) if m else "n/a"


def internal_chunks():
    """20 policies: one area per folder, header fields (ID, version, review date) copied to every chunk."""
    docs = []
    for pdf in sorted(INTERNAL.rglob("*.pdf")):
        pages = PyPDFLoader(str(pdf)).load()
        first = pages[0].page_content
        header = {
            "doc_id": header_field(first, "Document ID") or header_field(first, "Policy ID")
                      or header_field(first, "Policy reference") or "n/a",
            "version": header_field(first, "Version") or "n/a",
            "last_reviewed": last_reviewed_of(first),     # also reads "Last reviewed in August 2026"
        }
        for p in pages:
            p.metadata.update(header)
            p.metadata["source"] = str(pdf.relative_to(BASE))
            p.metadata["area"] = pdf.parent.name
            p.metadata["doc_title"] = pdf.stem.replace("IronStore_", "").replace("_", " ")
            p.metadata["doc_type"] = "internal"
            p.metadata["page"] = p.metadata["page"] + 1   # 1-based, the physical PDF page
        docs.extend(pages)
    return RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150).split_documents(docs)


def catalog_chunks():
    """63 catalogues: the 2021 edition is marked 'outdated' and filtered out at search time."""
    docs = []
    for pdf in sorted(CATALOG.glob("*.pdf")):
        pages = PyPDFLoader(str(pdf)).load()
        first = pages[0].page_content
        category = pdf.stem.replace("IronStore_Product_Catalog_", "").replace("_", " ")
        reviewed = last_reviewed_of(first)
        status = "outdated" if reviewed != "n/a" and int(reviewed[-4:]) < 2026 else "current"
        for p in pages:
            p.metadata.update({
                "source": str(pdf.relative_to(BASE)),
                "area": "product_catalog",
                "doc_title": f"Product Catalog - {category}",
                "doc_type": "catalog",
                "doc_id": header_field(first, "Internal catalog edition") or "n/a",
                "version": "n/a",
                "last_reviewed": reviewed,
                "status": status,
                "page": p.metadata["page"] + 1,
            })
            # the catalogue prints its own "Page N" labels, which differ from the PDF page: remove them
            p.page_content = re.sub(r"(?m)^Page \d+ [—-] ", "Section: ", p.page_content)
            p.page_content = f"[Catalog: {category}]\n" + p.page_content
        docs.extend(pages)
    return RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200).split_documents(docs)


if __name__ == "__main__":
    if DB.exists():
        shutil.rmtree(DB)                      # start clean: no duplicates, no leftover segments
    emb = OpenAIEmbeddings(model="text-embedding-3-small")
    internal = internal_chunks()
    Chroma.from_documents(internal, emb, collection_name="internal_docs", persist_directory=str(DB))
    print("internal chunks:", len(internal))
    catalog = catalog_chunks()
    Chroma.from_documents(catalog, emb, collection_name="product_catalog", persist_directory=str(DB))
    print("catalog chunks:", len(catalog),
          "| outdated:", sorted({c.metadata["doc_title"] for c in catalog if c.metadata["status"] == "outdated"}))
