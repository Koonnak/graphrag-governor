# API Reference — GraphRAG‑Governor

> **Goal:** Make it instantly clear what the API does, for both **non‑technical** and **technical** audiences.
> **Scope:** Public demo endpoints shipped with this repo (no auth). Production deployments should add TLS, authN/Z, and rate limiting.

---

## 1) Non‑Technical Overview (What this API does)

GraphRAG‑Governor answers questions about your documents. You send a **question**; the system **finds relevant passages** and **drafts an answer**, while measuring **quality, speed, and cost signals**. Two retrieval modes can be tried **side‑by‑side** (A/B) so you can pick what works best.

**Why this matters**

* **Trust:** Fewer hallucinations thanks to stronger retrieval and built‑in evaluations.
* **Speed & Cost:** Latency and (optional) token costs are tracked to optimize your spend.
* **Privacy by design:** Basic PII masking is applied on inputs/outputs.
* **Experimentation:** Toggle between variants to compare results fairly.

**How you use it**

* Call a single endpoint: `POST /query` with `{ "question": "..." }`.
* Choose retrieval **Variant A** (lexical/BM25) or **Variant B** (dense vectors/FAISS) via a URL parameter.
* Optionally choose **top‑K** passages (`k`) to balance recall vs. speed.
* Read the JSON response: an **answer**, **what variant was used**, **how fast it was**, and the **matched documents**.

---

## 2) Technical Reference (Full Details)

### 2.1 Base URL & OpenAPI UI

* **Base URL (local):** `http://localhost:8000`
* **OpenAPI UI:** `http://localhost:8000/docs` (Swagger UI)

### 2.2 Endpoints

* `POST /query` — Ask a question, control retrieval variant and top‑K.
* `GET  /health` — Liveness probe for Docker/ingress.

### 2.3 Content‑Type & Headers

* **Request:** `Content-Type: application/json`
* **Response:** `application/json; charset=utf-8`
* **Tracing (optional):** The service honors W3C `traceparent` if present. You can also send an `X-Request-ID` header for log correlation.

### 2.4 Security & Privacy (demo)

* **No authentication** in demo mode — add authN/Z at the reverse proxy or app layer in production.
* **PII masking:** regex‑based masking runs **pre** and **post** generation (emails, 13–16 digit card‑like numbers). Extend patterns carefully in production.
* **Logging/telemetry:** payloads are not intentionally copied into traces; still avoid secrets in prompts.

### 2.5 `POST /query`

Ask a question and retrieve an answer produced from the top‑K most relevant passages.

**Query parameters**

* `variant` (string, enum: `A`|`B`, default `A`)

  * `A` → **BM25** lexical retrieval (rank‑bm25)
  * `B` → **Dense** retrieval with **Sentence‑Transformers** + **FAISS** IP index
* `k` (integer, default `6`, typical range `3–20`)

  * Number of top documents/passages used for answer synthesis

**Request body**

```json
{
  "question": "Explain GDPR guarantees."
}
```

**Response body**

```json
{
  "answer": "Demo answer (from 3 passages): ...",
  "variant": "A",
  "k": 6,
  "hits": [["doc_0", 12.3], ["doc_1", 10.1], ["doc_2", 9.7]],
  "latency_ms": 42.1
}
```

**Field semantics**

* `answer` — A synthesized response (demo generator by default; plug your LLM provider in production).
* `variant` — Retrieval mode used (`A`=BM25, `B`=Dense/FAISS).
* `k` — Top‑K used for this run.
* `hits` — Array of `[doc_id, score]` pairs.

  * **Scores are backend‑specific** and not calibrated across variants

    * BM25: higher is better; magnitude is BM25‑specific
    * Dense/FAISS: inner‑product similarity; higher is better
* `latency_ms` — End‑to‑end wall‑clock time for this pipeline run.

**Examples**

* **Variant A (BM25), default K**

```bash
curl -s -X POST "http://localhost:8000/query?variant=A" \
  -H "Content-Type: application/json" \
  -d '{"question": "What privacy guarantees do you provide?"}' | jq
```

* **Variant B (Dense), K=8**

```bash
curl -s -X POST "http://localhost:8000/query?variant=B&k=8" \
  -H "Content-Type: application/json" \
  -d '{"question": "How do you evaluate answer quality?"}' | jq
```

**Validation & limits**

* `question`: non‑empty UTF‑8 string; recommended `1–4000` chars (practical guidance).
* Unknown query params are ignored; invalid `variant` → `400 Bad Request`.

**Error codes**

* `400 Bad Request` — Missing/invalid body or parameters
* `500 Internal Server Error` — Unhandled error (check logs and Jaeger traces)

**Error example**

```json
{
  "detail": "variant must match pattern ^[AB]$"
}
```

### 2.6 `GET /health`

Liveness probe for container orchestration.

**Request**

```
GET /health
```

**Response**

```json
{ "status": "ok" }
```

### 2.7 Observability & A/B Experimentation

* **Metrics (Prometheus via OTel Collector):**

  * `rag_requests_total` (Counter)
  * `rag_latency_ms` (Histogram)
* **Traces (Jaeger):** spans for `http_query`, `retrieve`, `gather_contexts`, `generate`.
* **A/B runs:** compare `variant=A` vs `variant=B` on the same questions; visualize latency distributions and evaluation scores (RAGAS) in Grafana/MLflow.

### 2.8 Versioning & Compatibility

* **API stability:** Demo endpoints are intentionally minimal and may evolve. Use **semantic version tags** at the repo level.
* **Forward compatibility hooks:** headers `traceparent`, `X-Request-ID` supported; room for `X-API-Version` and auth headers when you enable them.

### 2.9 Performance Tips

* Keep `k` small for low latency; increase `k` for harder queries.
* Use **Variant B** for semantically phrased questions; **Variant A** for keyword‑heavy prompts.
* Pre‑embed and cache documents; consider re‑ranking for best‑of‑both worlds (roadmap).

### 2.10 Security Notes (Production Hardening)

* Add **TLS**, **AuthN (OIDC)**, and **RBAC**; avoid exposing MLflow/Neo4j UIs to the public Internet.
* Restrict logs; scrub secrets/PII; set retention windows for Jaeger/Prometheus.
* Enforce rate limiting and request size limits at your gateway.

---

## 3) JSON Schemas (Contract)

**Request: /query**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.org/schemas/query.request.json",
  "type": "object",
  "required": ["question"],
  "properties": {
    "question": { "type": "string", "minLength": 1, "maxLength": 4000 }
  },
  "additionalProperties": false
}
```

**Response: /query**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.org/schemas/query.response.json",
  "type": "object",
  "required": ["answer", "variant", "k", "hits", "latency_ms"],
  "properties": {
    "answer": { "type": "string" },
    "variant": { "type": "string", "enum": ["A", "B"] },
    "k": { "type": "integer", "minimum": 1 },
    "hits": {
      "type": "array",
      "items": {
        "type": "array",
        "prefixItems": [ {"type": "string"}, {"type": "number"} ],
        "minItems": 2,
        "maxItems": 2
      }
    },
    "latency_ms": { "type": "number", "minimum": 0 }
  },
  "additionalProperties": true
}
```

---

## 4) Client Snippets

**Python (requests)**

```python
import requests

resp = requests.post(
    "http://localhost:8000/query",
    params={"variant": "B", "k": 8},
    json={"question": "How do you evaluate answer quality?"},
    headers={"Content-Type": "application/json"},
    timeout=20,
)
resp.raise_for_status()
print(resp.json())
```

**HTTPie**

```bash
http POST :8000/query variant==A k==6 question="Explain GDPR guarantees."
```

---

## 5) Troubleshooting

* **400 Bad Request**: Validate `variant` (A/B) and ensure `question` is a non‑empty string.
* **No metrics/traces**: Check OTel Collector service and `OTEL_EXPORTER_OTLP_ENDPOINT` in `.env`.
* **Neo4j unavailable**: Retrieval still works over text index; KG‑specific features will be limited.

---

## 6) Roadmap Flags (Non‑Breaking)

* Cross‑encoder re‑ranking, HNSW index, hybrid fusion.
* Cost/tokens telemetry and per‑request cost estimates.
* AuthN/Z, rate limiting, request size limits.
* RL Auto‑Tuner (PPO): policy control over `k`, fusion weights, and prompts.

