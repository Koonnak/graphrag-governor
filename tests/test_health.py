"""Sanity tests for the FastAPI app: liveness, query flow, and basic schema.

These tests exercise:
  - /health liveness semantics and payload.
  - /query happy paths for both retrieval variants (A/B).
  - Input validation (invalid variant) and top-k behavior.

Run:
  pytest -q
"""
from __future__ import annotations

from http import HTTPStatus
from typing import Any, Dict, List

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_health_ok() -> None:
    """Verify that /health returns 200 and a minimal status payload.

    Ensures:
      - HTTP 200 status.
      - JSON body contains {"status": "ok"}.
    """
    r = client.get("/health")
    assert r.status_code == HTTPStatus.OK
    body = r.json()
    assert isinstance(body, dict)
    assert body.get("status") == "ok"


def _assert_query_response_schema(data: Dict[str, Any]) -> None:
    """Common assertions for /query response shape.

    Args:
      data: Parsed JSON response.

    Ensures:
      - Required keys exist with expected types.
      - `hits` is a list of {doc_id, score}.
      - `k` matches the number of hits.
    """
    assert isinstance(data, dict)
    for key in ("answer", "variant", "k", "hits", "latency_ms"):
        assert key in data, f"Missing key in response: {key}"

    assert isinstance(data["answer"], str)
    assert data["variant"] in {"A", "B"}
    assert isinstance(data["k"], int) and data["k"] >= 1
    assert isinstance(data["latency_ms"], (int, float)) and data["latency_ms"] >= 0

    hits: List[Dict[str, Any]] = data["hits"]
    assert isinstance(hits, list)
    assert len(hits) == data["k"]
    for h in hits:
        assert isinstance(h, dict)
        assert "doc_id" in h and isinstance(h["doc_id"], str)
        assert "score" in h and isinstance(h["score"], (int, float))


def test_query_variant_a() -> None:
    """Happy path: variant A (BM25) returns a structured response."""
    r = client.post("/query?variant=A&k=3", json={"question": "What is this demo about?"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    _assert_query_response_schema(data)


def test_query_variant_b() -> None:
    """Happy path: variant B (dense) returns a structured response."""
    r = client.post("/query?variant=B&k=2", json={"question": "Tell me about privacy & GDPR."})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    _assert_query_response_schema(data)


def test_query_invalid_variant_is_rejected() -> None:
    """Input validation: invalid variant should raise 422 (FastAPI Query pattern)."""
    r = client.post("/query?variant=Z", json={"question": "Hello?"})
    assert r.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_query_topk_clamping_and_types() -> None:
    """Top-k behavior: k is clamped to corpus size and reflected in hits length.

    Requests a large k; response should:
      - remain 200 OK,
      - have `k` >= 1 and <= requested upper bound,
      - have `len(hits) == k`.
    """
    requested_k = 999
    r = client.post(f"/query?variant=A&k={requested_k}", json={"question": "What do you know?"})
    assert r.status_code == HTTPStatus.OK
    data = r.json()
    _assert_query_response_schema(data)
    assert 1 <= data["k"] <= requested_k
    assert len(data["hits"]) == data["k"]

