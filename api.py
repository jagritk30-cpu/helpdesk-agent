"""
FastAPI REST API for the HR/IT Helpdesk Agent.
Endpoints:
  POST /chat          — Send a message to the agent
  POST /admin/ingest  — Re-ingest policy documents into ChromaDB
  GET  /health        — Health check
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.agent import run_agent
from agent.rag import build_vectorstore

app = FastAPI(
    title="HR/IT Helpdesk Agent",
    description="An AI-powered HR and IT support agent with RAG, MCP, and guardrails.",
    version="1.0.0",
)

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's question")
    history: list[dict] | None = Field(
        default=None,
        description="Optional conversation history in OpenAI message format",
    )


class ChatResponse(BaseModel):
    reply: str
    blocked: bool = False
    block_reason: str | None = None


class IngestResponse(BaseModel):
    status: str
    message: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the modern interactive Helpdesk UI."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>Helpdesk Agent API Running. UI not found.</h1>")


@app.get("/health")
def health():
    return {"status": "ok", "service": "HR/IT Helpdesk Agent"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Send a message to the helpdesk agent."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        reply = run_agent(req.message, req.history)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.post("/admin/ingest", response_model=IngestResponse)
def ingest(force: bool = False):
    """Re-ingest policy documents into the vector store."""
    try:
        build_vectorstore(force_rebuild=force)
        return IngestResponse(
            status="success",
            message="Policy documents ingested into ChromaDB successfully.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    import os
    uvicorn.run(
        "api:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=True,
    )
