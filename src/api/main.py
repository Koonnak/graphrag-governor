"""FastAPI application entrypoint.

Overview:
  Small, production-lean API exposing a demo GraphRAG pipeline.

Endpoints:
  - GET /health
      Liveness probe used by the Docker healthcheck.
  - POST /query
      Query endpoint with A/B retrieval switch and configurable top-k.

Usage:
  curl -s -X POST 'http://localhost:8000/query?variant=B&k=5' \
    -H 'Content-Type: application/json' \
    -d '{"question":"What are the privacy guarantees?"}'
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.pipelines.rag import RAGPipeline, Retriever

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
# Minimal logging setup (for richer logs, wire structlog + JSON formatter).
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("graphrag-gov")

# -----------------------------------------------------------------------------
# Demo corpus bootstrap
# -----------------------------------------------------------------------------
DOC_PATHS: List[str] = [
    "data/sample_docs/00_intro.md",
    "data/sample_docs/01_architecture.md",
    "data/sample_docs/02_privacy.md",
]
DOCS: List[str] = []
IDS: List[str] = []

for i, fp in enumerate(DOC_PATHS):
    try:
        with open(fp, "r", encoding="utf-8") as f:
            DOCS.append(f.read())
            IDS.append(f"doc_{i}")
    except FileNotFoundError:
        # Continue; we will fall back to placeholders if none are found.
        pass

if not DOCS:
    logger.warning("Sample docs not found — using placeholders")
    DOCS = [
        "Welcome to GraphRAG-Governor demo.",
        "Architecture placeholder.",
        "Privacy placeholder.",
    ]
    IDS = [f"doc_{i}" for i in range(len(DOCS))]

# Build pipeline singletons
retriever = Retriever(DOCS, IDS)
pipeline = RAGPipeline(retriever)

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(
    title="GraphRAG-Governor",
    version="0.1.0",
    summary="Production-lean GraphRAG demo API",
    description=(
        "A minimal API exposing a GraphRAG retrieval-and-generation pipeline "
        "with A/B retrieval variants and basic guardrails/observability."
    ),
)

# Optional CORS for local UI testing (tighten for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your UI origin(s)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------
class QueryIn(BaseModel):
    """Input payload for /query."""

    question: str = Field(..., description="User question to answer.")


class Hit(BaseModel):
    """Single retrieval hit."""

    doc_id: str = Field(..., description="Identifier of the matched document.")
    score: float = Field(..., description="Backend-specific relevance score.")


class QueryOut(BaseModel):
    """Structured response of /query."""

    answer: str = Field(..., description="Final answer after guardrails.")
    variant: str = Field(..., description='Retrieval variant used: "A" (BM25) or "B" (Dense).')
    k: int = Field(..., description="Number of contexts considered.")
    hits: List[Hit] = Field(..., description="Top-k retrieval results.")
    latency_ms: float = Field(..., description="End-to-end latency in milliseconds.")


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    """Liveness endpoint.

    Returns:
      dict: A simple status payload used by Docker's HEALTHCHECK.
    """
    return {"status": "ok"}


@app.post("/query", response_model=QueryOut)
def query(
    q: QueryIn,
    variant: str = Query(
        "A",
        pattern="^[AB]$",
        description='Retrieval variant: "A"=BM25 or "B"=Dense vectors.',
    ),
    k: int = Query(
        6,
        ge=1,
        le=100,
        description="Top-k contexts to retrieve (clamped to corpus size).",
    ),
) -> QueryOut:
    """Answer a question using the selected retrieval variant.

    The pipeline applies guardrails (pre/post), retrieves top-k contexts,
    generates a draft answer (placeholder), and reports observability metrics.

    Args:
      q: Input payload with the user question.
      variant: Retrieval variant to use ("A" or "B").
      k: Number of contexts to retrieve (1..100; clamped to corpus size).

    Returns:
      QueryOut: Structured answer and execution metadata.

    Notes:
      - For production quality, add re-ranking and cite-span offsets.
      - Scores are variant-specific and not cross-comparable.
    """
    # Clamp k to the available corpus size to avoid empty padding.
    k_eff = max(1, min(k, len(IDS)))
    result = pipeline.run(q.question, variant=variant, k=k_eff)

    # Convert tuple hits -> structured list for response_model fidelity.
    hits_struct = [Hit(doc_id=doc_id, score=score) for doc_id, score in result["hits"]]

    return QueryOut(
        answer=result["answer"],
        variant=result["variant"],
        k=result["k"],
        hits=hits_struct,
        latency_ms=result["latency_ms"],
    )

