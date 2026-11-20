"""
RAG pipeline — builds and queries the ChromaDB vector store
from HR/IT policy documents using Google Gemini embeddings (free).
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

POLICY_DIR = Path(__file__).parent.parent / "data" / "policies"
CHROMA_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
COLLECTION_NAME = "hr_it_policies"


def get_vectorstore(persist_directory: str = CHROMA_DIR) -> Chroma:
    """Return (or build) the ChromaDB vector store using Gemini embeddings."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key or api_key == "your-gemini-api-key-here":
        raise ValueError(
            "GOOGLE_API_KEY is not configured. Please add your key to .env. "
            "You can get a free key at https://aistudio.google.com"
        )
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=persist_directory,
    )


def build_vectorstore(force_rebuild: bool = False) -> Chroma:
    """
    Ingest all policy documents from data/policies/ into ChromaDB.
    Skips rebuild if already populated (unless force_rebuild=True).
    """
    vectorstore = get_vectorstore()

    # Check if already populated
    existing = vectorstore.get()
    if existing["ids"] and not force_rebuild:
        print(f"[RAG] Vector store already has {len(existing['ids'])} chunks. Skipping rebuild.")
        return vectorstore

    print("[RAG] Building vector store from policy documents…")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
        separators=["\n─", "\n\n", "\n", " "],
    )

    all_docs = []
    policy_files = list(POLICY_DIR.glob("*.txt")) + list(POLICY_DIR.glob("*.pdf"))

    if not policy_files:
        raise FileNotFoundError(f"No policy files found in {POLICY_DIR}")

    for filepath in policy_files:
        print(f"  → Loading {filepath.name}")
        text = filepath.read_text(encoding="utf-8")
        chunks = splitter.create_documents(
            texts=[text],
            metadatas=[{"source": filepath.name, "doc_type": "policy"}],
        )
        all_docs.extend(chunks)

    print(f"[RAG] Adding {len(all_docs)} chunks to ChromaDB…")
    vectorstore.add_documents(all_docs)
    print("[RAG] Vector store built successfully.")
    return vectorstore


def retrieve_policy_context(query: str, k: int = 4) -> list[dict]:
    """
    Retrieve the top-k most relevant policy chunks for a query.
    Returns list of dicts with 'content' and 'source' keys.
    """
    vectorstore = get_vectorstore()
    results = vectorstore.similarity_search_with_score(query, k=k)
    return [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source", "unknown"),
            "score": float(score),
        }
        for doc, score in results
    ]


if __name__ == "__main__":
    build_vectorstore(force_rebuild=True)
    print("\nTest retrieval for 'how many annual leave days do I get?':")
    hits = retrieve_policy_context("how many annual leave days do I get?")
    for h in hits:
        print(f"\n[{h['source']}] score={h['score']:.3f}")
        print(h["content"][:300])
