"""GraphRAG retrieval-and-generation pipeline (demo baseline).

Overview:
  This module wires a minimal, provider-agnostic RAG pipeline with two retrieval
  backends and a placeholder generator. It is designed to be production-lean
  (observable, testable) while keeping the surface area small for demos.

Strategy:
  - A/B retrieval variants:
      A) BM25 (lexical)
      B) Dense vectors (Sentence-Transformers + FAISS IP)
  - Generation is a stub; swap in a real LLM call for production.
  - Observability: OTel spans for key stages + request count/latency metrics.

Limitations:
  - No re-ranking step (add a cross-encoder if needed).
  - No cite-span tracking yet (IDs are returned for hits, not offsets).

Example:
  pipeline = RAGPipeline(Retriever(docs, ids))
  result = pipeline.run("What is the privacy policy?", variant="B", k=6)
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import time

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from src.guardrails.policy import PolicyEngine
from src.obs.otel import rag_latency_ms, rag_requests_total, tracer

# Type alias for readability: (document_id, score)
Hit = Tuple[str, float]

# Default dense model used for the demo backend.
DEFAULT_ST_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class VectorStore:
    """Simple FAISS inner-product index with L2-normalized embeddings.

    The store assumes cosine-like scoring via L2-normalization + inner product.

    Attributes:
      index: FAISS index initialized for inner-product search.
      ids: Parallel list of document IDs aligned with the embeddings matrix.

    Args:
      embeddings: 2D NumPy array of shape (N, D); will be L2-normalized in place.
      ids: List of length N with stable string identifiers for each embedding.

    Raises:
      ValueError: If `embeddings` is not 2D or `len(ids)` != `embeddings.shape[0]`.
    """

    def __init__(self, embeddings: np.ndarray, ids: List[str]) -> None:
        if embeddings.ndim != 2 or len(ids) != embeddings.shape[0]:
            raise ValueError("Embeddings shape and ids length must match")
        self.index = faiss.IndexFlatIP(embeddings.shape[1])
        faiss.normalize_L2(embeddings)  # in-place normalization
        self.index.add(embeddings)
        self.ids = ids

    def search(self, qvec: np.ndarray, k: int = 5) -> List[Hit]:
        """Search top-k nearest neighbors for a single query vector.

        Args:
          qvec: Query vector of shape (D,) or batch (1, D).
          k: Number of hits to return (clamped to index size).

        Returns:
          List of (doc_id, score) sorted by decreasing score.

        Notes:
          - Input `qvec` will be L2-normalized prior to search.
        """
        if qvec.ndim == 1:
            qvec = qvec[None, :]
        faiss.normalize_L2(qvec)
        k = max(1, min(k, len(self.ids)))
        D, I = self.index.search(qvec, k)
        return [(self.ids[i], float(D[0][j])) for j, i in enumerate(I[0])]


class Retriever:
    """Composable retriever exposing BM25 and dense-vector backends.

    The retriever owns:
      - A BM25Okapi instance for lexical matching (variant "A").
      - A Sentence-Transformers encoder + FAISS index for dense search (variant "B").

    Attributes:
      docs: Corpus texts aligned with `ids`.
      ids: Stable document identifiers.
      id2pos: Fast lookup mapping from id -> position in `docs`.

    Args:
      docs: List of corpus documents (non-empty).
      ids: List of unique IDs, same length/order as `docs`.

    Raises:
      ValueError: If `docs` is empty.
    """

    def __init__(self, docs: List[str], ids: List[str]) -> None:
        if not docs:
            raise ValueError("Empty corpus: provide at least 1 document")
        self.docs = docs
        self.ids = ids
        self.id2pos = {d_id: i for i, d_id in enumerate(ids)}

        # Lexical backend
        self.bm25 = BM25Okapi([d.split() for d in docs])

        # Dense backend
        self.model = SentenceTransformer(DEFAULT_ST_MODEL)
        embs = self.model.encode(docs, convert_to_numpy=True, normalize_embeddings=False)
        self.vs = VectorStore(embs, ids)

    def retrieve(self, query: str, k: int = 6, variant: str = "A") -> List[Hit]:
        """Retrieve top-k hits for a query using the selected variant.

        Args:
          query: User query string.
          k: Number of hits to return; clamped to corpus size.
          variant: "A" for BM25 (lexical) or "B" for dense vectors.

        Returns:
          List of (doc_id, score) pairs in descending score order.

        Notes:
          - BM25 scores are not comparable with dense scores; use per-variant A/B.
        """
        k = max(1, min(k, len(self.ids)))
        if variant == "A":
            scores = self.bm25.get_scores(query.split())
            topk = np.argsort(scores)[-k:][::-1]
            return [(self.ids[i], float(scores[i])) for i in topk]

        # Variant B: dense vectors
        q = self.model.encode([query], convert_to_numpy=True)
        return self.vs.search(q, k=k)

    def contexts_for(self, hit_ids: List[str]) -> List[str]:
        """Resolve contexts (raw docs) for a list of hit IDs.

        Args:
          hit_ids: Document identifiers returned by `retrieve()`.

        Returns:
          List of document texts aligned with `hit_ids`. Missing IDs are ignored.
        """
        ctxs: List[str] = []
        for d_id in hit_ids:
            pos = self.id2pos.get(d_id)
            if pos is not None:
                ctxs.append(self.docs[pos])
        return ctxs


class Generator:
    """Minimal placeholder generator.

    Replace `generate()` with a real LLM call (LiteLLM/OpenAI/Azure/HF) to
    move beyond the demo. Keep the interface unchanged to avoid breaking
    the pipeline or observability.
    """

    def generate(self, question: str, contexts: List[str]) -> str:
        """Concatenate contexts and return a truncated demo answer.

        Args:
          question: The sanitized user question (after guardrails).
          contexts: Retrieved passages used to ground the answer.

        Returns:
          A demo string summarizing how many passages were used and their head.
        """
        ctx = "\n---\n".join(contexts)
        return f"Demo answer (from {len(contexts)} passages):\n{ctx[:800]}\n..."


class RAGPipeline:
    """End-to-end RAG runner with observability and guardrails.

    Responsibilities:
      - Apply pre-enforcement guardrails (e.g., PII masking).
      - Retrieve top-k contexts (BM25 or Dense).
      - Generate an answer (placeholder).
      - Apply post-enforcement guardrails.
      - Emit OTel spans/metrics for each stage.

    Args:
      retriever: Configured `Retriever` instance.
      policy: Optional policy engine; defaults to `PolicyEngine()`.

    Example:
      pipeline = RAGPipeline(Retriever(docs, ids))
      res = pipeline.run("What is privacy?", variant="A", k=5)
    """

    def __init__(self, retriever: Retriever, policy: PolicyEngine | None = None) -> None:
        self.retriever = retriever
        self.generator = Generator()
        self.policy = policy or PolicyEngine()

    def run(self, question: str, variant: str = "A", k: int = 6) -> Dict:
        """Execute the RAG flow for a single query.

        Args:
          question: Raw user question.
          variant: Retrieval variant ("A"=BM25, "B"=Dense).
          k: Number of contexts to retrieve (clamped to corpus size).

        Returns:
          Dict with keys:
            - answer (str): Final, post-enforced answer text.
            - variant (str): The retrieval variant used ("A" or "B").
            - k (int): Number of retrieved contexts considered.
            - hits (List[Hit]): (doc_id, score) pairs.
            - latency_ms (float): End-to-end latency in milliseconds.

        Notes:
          - For production, attach cite-spans and re-ranking for higher quality.
        """
        with tracer.start_as_current_span("rag_query") as span:
            rag_requests_total.add(1)
            t0 = time.time()

            q_clean = self.policy.pre_enforce(question)
            span.set_attribute("variant", variant)
            span.set_attribute("k", k)

            # Retrieval stage
            with tracer.start_as_current_span("retrieve"):
                hits = self.retriever.retrieve(q_clean, k=k, variant=variant)

            # Context assembly stage
            with tracer.start_as_current_span("gather_contexts"):
                hit_ids = [doc_id for doc_id, _ in hits]
                contexts = self.retriever.contexts_for(hit_ids)

            # Generation stage
            with tracer.start_as_current_span("generate"):
                answer = self.generator.generate(q_clean, contexts)

            # Post-enforcement stage
            answer = self.policy.post_enforce(answer)

            # Metrics
            latency = (time.time() - t0) * 1000.0
            rag_latency_ms.record(latency)
            span.set_attribute("latency_ms", round(latency, 1))

            return {
                "answer": answer,
                "variant": variant,
                "k": k,
                "hits": hits,
                "latency_ms": round(latency, 1),
            }

