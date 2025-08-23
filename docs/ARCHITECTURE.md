# GraphRAG‑Governor — Architecture

> **Audience:** Non‑technical leaders *and* technical stakeholders. This document provides a high‑level narrative first, then a deep technical breakdown with precise component responsibilities and interfaces.

---

## 1) Executive Summary (Non‑Technical)

**What this system does.** GraphRAG‑Governor is a command center for AI answers over your documents. It retrieves evidence from your content, drafts an answer, and monitors quality, speed, and cost. You can A/B test retrieval strategies to pick the best configuration. Privacy is baked in via PII masking; operations are visible via dashboards.

**Why it matters.**

* **Trust:** Fewer hallucinations through better retrieval and continuous evaluation.
* **Efficiency:** Monitors latency and (optionally) token cost to control spend.
* **Compliance:** GDPR‑aware defaults (PII redaction, minimal logging); runs are auditable.
* **Operability:** Clear health checks, metrics, and traces; one‑click local environment.

**What it is not.** A final business UI. It’s a production‑style *control plane* and API foundation you can connect to your own apps and data pipelines.

---

## 2) System Overview (Technical)

**Core services (docker‑compose)**

* **API (FastAPI + Gunicorn/Uvicorn):** `/query`, `/health`, OpenAPI docs. Stateless.
* **Retrieval Engines (in‑process):**

  * **Variant A:** BM25 (lexical retrieval via `rank‑bm25`).
  * **Variant B:** Dense retrieval (Sentence‑Transformers `all‑MiniLM‑L6‑v2`) + FAISS IP index.
* **Generator (pluggable):** Demo composer by default; swap with OpenAI/Azure/HF/LiteLLM.
* **Guardrails:** Pre/post PII masking; hooks for LLM‑as‑judge/policy.
* **Knowledge Graph:** Neo4j (minimal `(:Document {id,title})` schema) + RDF export (RDFLib).
* **Observability:** OpenTelemetry SDK → OTel Collector → Jaeger (traces), Prometheus (metrics) → Grafana.
* **Evaluation:** RAGAS metrics and MLflow tracking (experiments/runs/artifacts).

**External interfaces**

* **Northbound:** HTTP/JSON clients (apps, Postman, curl), Grafana, MLflow UI, Jaeger, Neo4j Browser.
* **Southbound:** Optional LLM provider, object stores or vector DBs (future), identity providers (OIDC, future).

---

## 3) Logical Architecture Diagram

```
[ Client / UI ]
      |
      v
[ FastAPI API ] --(OTel SDK)--> [ OTel Collector ] --> [ Jaeger ] (traces)
      |                                          \--> [ Prometheus ] --> [ Grafana ] (metrics)
      v
[ RAG Pipeline ] -----> [ Guardrails (PII, policy, LLM‑judge hooks) ]
   |      \
   |       \---> [ Retriever A: BM25 ] ----+
   |                                       |--> [ Merge / select variant ] --> [ Generator (LLM stub or provider) ]
   |       /---> [ Retriever B: Dense + FAISS ]-
   |
   +--> [ Knowledge Graph (Neo4j) ] --(export)--> [ RDF / Triple Store (optional) ]

[ Evaluation: RAGAS + MLflow ] (runs, metrics, artifacts)
```

---

## 4) Request Lifecycle (Sequence)

```
Client -> API(POST /query?variant=A|B&k=N)
API -> Guardrails.pre_enforce(question)          # PII masking
API -> Retriever.retrieve(variant, k, question)  # BM25 or Dense/FAISS
API -> ContextGatherer (map ids -> passages)
API -> Generator.generate(question, contexts)    # LLM stub or provider call
API -> Guardrails.post_enforce(answer)           # PII masking
API -> Telemetry (latency, counters, spans)
API -> Client (JSON: answer, variant, k, hits, latency_ms)
```

**Traced spans:** `http_query` → `retrieve` → `gather_contexts` → `generate`.
**Metrics:** `rag_requests_total` (Counter), `rag_latency_ms` (Histogram).

---

## 5) Data Model & Storage

**Documents (demo):**

* Files: `data/sample_docs/*.md` (seed content).
* Vector embeddings: computed from Sentence‑Transformers; in‑memory FAISS IP index.
* Lexical index: BM25 token arrays (in‑memory) for fast scoring.

**Knowledge Graph:**

* Minimal label: `(:Document { id: STRING, title: STRING })`.
* Extend with relations: `(:Concept)`, `(:Company)`, edges `(:Document)-[:MENTIONS]->(:Concept)`.
* RDF export: Turtle serialization for triple‑store interoperability.

**Evaluation & Telemetry:**

* **MLflow:** experiments/runs; params (variant, k), metrics (RAGAS), artifacts.
* **Jaeger/Prometheus:** traces and runtime metrics (latency, throughput, errors).

**PII handling:** input/output masking; redact secrets from logs; avoid raw payloads in traces.

---

## 6) Component Responsibilities & Interfaces

* **`src/api`**: request validation, routing, CORS; orchestrates pipeline and telemetry; returns JSON.
* **`src/pipelines`**: retrieval orchestration and generation call; variant selection; k‑control; timing.
* **`src/guardrails`**: pre/post enforcement (PII). Extension hooks for policy & LLM‑judge.
* **`src/obs`**: OTel setup; tracer/meter providers; metric creation.
* **`src/kg`**: Neo4j client wrapper; RDF export utilities.
* **`src/eval`**: RAGAS evaluation runner; MLflow logging.
* **`scripts/`**: utilities (embedding bootstrap, etc.).

**Key interfaces (selected)**

* `RAGPipeline.run(question: str, variant: str, k: int) -> Dict`
* `Retriever.retrieve(query: str, k: int, variant: str) -> List[Tuple[str, float]]`
* `PolicyEngine.pre_enforce(text: str) -> str`; `post_enforce(text: str) -> str`

---

## 7) Configuration & Environment

**Environment variables (see `.env.example`):** `OTEL_EXPORTER_OTLP_ENDPOINT`, `SERVICE_NAME`, `NEO4J_URI`, `MLFLOW_TRACKING_URI`, optional LLM settings.

**Ports (defaults):** API 8000; Neo4j 7474/7687; MLflow 5000; Jaeger 16686; Prometheus 9090; Grafana 3000; OTel gRPC 4317.

**Security (prod guidance):** terminate TLS at ingress; add OIDC SSO + RBAC; restrict UIs (Grafana/MLflow/Neo4j) to private networks.

---

## 8) Non‑Functional Requirements

* **Reliability:** health checks; graceful degradation when OTel or Neo4j are down.
* **Scalability:** stateless API behind load balancer; horizontal scale; shard/partition indices for large corpora.
* **Performance:** low‑latency retrieval; choose `k` per use‑case; cache embeddings & answers.
* **Observability:** standardized names, low‑cardinality labels; ready Grafana panels.
* **Security/Privacy:** data minimization, PII redaction, secret handling via platform vault.
* **Portability:** Docker images; clear service boundaries; env‑driven configuration.

---

## 9) Performance & Capacity Planning

* **CPU‑only baseline:** all‑MiniLM‑L6‑v2; FAISS IP; bm25 tokenization; sub‑100ms retrieval for small corpora.
* **GPU benefits:** faster embedding & cross‑encoder re‑ranking (future); batch offline indexing.
* **Scaling patterns:**

  * **Throughput:** N× API replicas (Gunicorn workers) + async I/O for LLM calls.
  * **Index:** switch to HNSW or a vector DB beyond \~1M passages; pre‑warm caches.
  * **Caching:** Redis for embeddings/answers; target 30–60% hit ratio.

---

## 10) Failure Modes & Fallbacks

* **OTel Collector unavailable:** API serves traffic; switches to no‑op telemetry.
* **Neo4j unavailable:** KG‑specific features degrade; core text retrieval intact.
* **LLM provider errors (when enabled):** apply retries/backoff; fail over to cached summaries where applicable.
* **High latency spikes:** reduce `k`, disable re‑ranking, increase workers, enforce timeouts.

---

## 11) Extensibility Roadmap

* **Re‑ranking:** cross‑encoder (`ms‑marco‑MiniLM‑L‑6‑v2`) on top‑N; hybrid fusion (lexical + dense).
* **Async pipeline:** concurrent retrieval/LLM; streaming responses (server‑sent events).
* **Knowledge Graph enrichment:** NER/RE pipelines, entity linking, link prediction (GraphSAGE/ComplEx).
* **Security:** OIDC, RBAC, per‑tenant namespaces; signed audit logs.
* **RL Auto‑Tuner:** PPO policy over `(k, fusion weights, prompt template)` using multi‑objective reward.

---

## 12) Testing Strategy & CI/CD

* **Unit:** guardrails, retriever adapters, config loaders.
* **Integration:** API `/health` and `/query` flows with seeded docs; FAISS/BM25 parity checks.
* **Evaluation pipelines:** deterministic slices; MLflow artifacts for regressions.
* **Load testing:** latency SLOs (P50/P95) using k6/Locust; variant A/B comparisons.
* **CI:** Ruff + Black + mypy + pytest; PR checks required; semantic version tags on release.

---

## 13) Deployment Topologies

* **Local (compose):** default; all services on a single host.
* **Single‑VM (prod‑like):** API behind Nginx/Traefik; MLflow/Neo4j restricted to private network.
* **Kubernetes (outline):** Deployments (API), StatefulSets (Neo4j), Services, Ingress, Secrets; OTel/Prometheus/Grafana via Helm charts.

---

## 14) SLOs & Dashboards

* **SLO examples:** P95 latency < 500 ms; error rate < 1%; availability > 99.9%.
* **Grafana panels:** API throughput, P50/P95 `rag_latency_ms`, error budget burn, A/B variant comparison, RAGAS score trend (from MLflow export).

---

## 15) ADR Index (Architecture Decision Records)

* **ADR‑001:** Provider‑agnostic generator stub to keep the core vendor‑neutral.
* **ADR‑002:** Two‑track retrieval (BM25 + Dense) for A/B clarity and coverage.
* **ADR‑003:** Observability via OTel Collector to unify traces/metrics export paths.
* **ADR‑004:** Minimal KG schema with RDF export to enable gradual semantic enrichment.

---

## 16) Glossary

* **RAG:** Retrieval‑Augmented Generation – LLM answers grounded in retrieved context.
* **BM25:** Probabilistic lexical ranking function for term matching.
* **FAISS (IP):** Facebook AI Similarity Search (Inner Product index for dense vectors).
* **OpenTelemetry (OTel):** Unified API/SDK for traces/metrics/logs.
* **Jaeger/Prometheus/Grafana:** Tracing backend / metrics store / dashboards.
* **MLflow/RAGAS:** Experiment tracking / RAG evaluation metrics.
* **Neo4j/RDF:** Property graph database / semantic web data model.

