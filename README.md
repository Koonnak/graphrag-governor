# GraphRAG‑Governor

> **Production‑grade Graph‑augmented RAG control plane** for reliable answers over your documents — with observability (OTel → Prometheus/Grafana/Jaeger), evaluation (RAGAS + MLflow), GDPR guardrails, and A/B testing. **Roadmap:** RL Auto‑Tuner (PPO) to optimize **cost ↔ quality ↔ latency**.

<p align="center">
  <!-- Replace YOUR-ORG/YOUR-REPO after pushing to GitHub -->
  <a href="[https://github.com/YOUR-ORG/YOUR-REPO/actions/workflows/ci.yml](https://github.com/Koonnak/graphrag-kg-CICD.git)"><img alt="CI" src="[https://img.shields.io/github/actions/workflow/status/YOUR-ORG/YOUR-REPO/ci.yml?label=CI&logo=github](https://github.com/Koonnak/graphrag-kg-CICD.git)" /></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11-blue" />
  <img alt="License" src="https://img.shields.io/badge/License-Apache--2.0-green" />
</p>

---

## Contents

* [TL;DR (Non‑Technical)](#tldr-non-technical)
* [TL;DR (Technical)](#tldr-technical)
* [Quickstart](#quickstart)
* [Documentation](#documentation)
* [Features](#features)
* [Minimal API (peek)](#minimal-api-peek)
* [Repository Structure](#repository-structure)
* [Configuration](#configuration)
* [Screenshots](#screenshots)
* [Troubleshooting / FAQ](#troubleshooting--faq)
* [Compatibility Matrix](#compatibility-matrix)
* [Roadmap](#roadmap)
* [Contributing](#contributing)
* [Maintainers & Support](#maintainers--support)
* [License](#license)

---

## TL;DR (Non‑Technical)

* **Fewer hallucinations, faster answers, predictable costs.**
* **Privacy by design:** PII masking; audit trails of experiments.
* **A/B experiments** to pick the best configuration with evidence.

## TL;DR (Technical)

* **Retrieval:** BM25 (A) + Dense/FAISS (B), top‑K control, hybrid‑ready.
* **Observability:** OpenTelemetry traces/metrics → Jaeger/Prometheus/Grafana.
* **Evaluation:** RAGAS + MLflow; dataset‑driven experiments and reports.
* **Guardrails:** pre/post PII redaction; policy hooks; provider‑agnostic generator.

---

## Quickstart

```bash
# 1) Configure
cp .env.example .env

# 2) Launch stack (API, Neo4j, MLflow, OTel, Jaeger, Prometheus, Grafana)
docker compose up -d --build

# 3) (Optional) Embed sample docs for dense retrieval demo
python scripts/bootstrap_index.py

# 4) Query (A = BM25, B = Dense)
curl -s -X POST "http://localhost:8000/query?variant=A&k=6" \
  -H "Content-Type: application/json" \
  -d '{"question":"What privacy guarantees do you provide?"}' | jq
```

### Local dev (without Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # or leave default
uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

**Local UIs**

* API Docs: `http://localhost:8000/docs`
* Neo4j: `http://localhost:7474` (neo4j/test)
* MLflow: `http://localhost:5000`
* Jaeger: `http://localhost:16686`
* Prometheus: `http://localhost:9090`
* Grafana: `http://localhost:3000`

---

## Documentation

> Full details, split for **non‑tech** and **tech** audiences.

* 📜 **API Reference:** [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)
* 🧭 **Architecture:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
* 📈 **Observability:** [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md)
* ⚙️ **Operations:** [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
* 🧪 **Evaluation:** [`docs/EVALUATION.md`](docs/EVALUATION.md)
* 🔭 **RL Auto‑Tuner (PPO) Roadmap:** [`docs/ROADMAP_RL_AUTOTUNER.md`](docs/ROADMAP_RL_AUTOTUNER.md)

---

## Features

* **A/B Retrieval Variants:** `variant=A|B` & `k` to trade recall vs. latency.
* **Knowledge‑Graph Ready:** Neo4j client + RDF export utilities.
* **Observability‑First:** standardized metrics (`rag_requests_total`, `rag_latency_ms`) and OTel spans.
* **Evaluation Harness:** RAGAS metrics logged to MLflow; experiment‑as‑code.
* **GDPR Guardrails:** pre/post PII masking, minimal payload logging, clear data flows.
* **Docker‑First:** one‑click stack; non‑root image; health checks.

---

## Minimal API (peek)

```http
POST /query?variant=A|B&k=6
Content-Type: application/json

{"question": "Explain GDPR guarantees."}
```

**Response**

```json
{
  "answer": "Demo answer (from 3 passages): ...",
  "variant": "A",
  "k": 6,
  "hits": [["doc_0", 12.3], ["doc_1", 10.1], ["doc_2", 9.7]],
  "latency_ms": 42.1
}
```

See full contract and examples in [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

---

## Repository Structure

```
.
├─ src/
│  ├─ api/            # FastAPI app, endpoints, CORS
│  ├─ pipelines/      # Retrieval & generation orchestration (A/B, k)
│  ├─ guardrails/     # PII masking + policy hooks
│  ├─ obs/            # OpenTelemetry wiring
│  ├─ kg/             # Neo4j client + RDF bridge
│  └─ eval/           # RAGAS + MLflow harness
├─ scripts/           # Utilities (bootstrap embeddings)
├─ data/sample_docs/  # Seed docs for demo
├─ docs/              # Architecture, API, Ops, Observability, Eval, GDPR, RL Roadmap
├─ docker-compose.yml
├─ Dockerfile
├─ prometheus.yml
├─ otel-collector-config.yaml
├─ requirements.txt
├─ .pre-commit-config.yaml
├─ pyproject.toml
└─ .github/workflows/ci.yml
```

---

## Configuration

| Variable                          | Purpose                          | Default                                |
| --------------------------------- | -------------------------------- | -------------------------------------- |
| `OTEL_EXPORTER_OTLP_ENDPOINT`     | OTel collector (gRPC)            | `http://otel-collector:4317`           |
| `SERVICE_NAME`                    | service.name for OTel            | `graph-rag-governor`                   |
| `NEO4J_URI` / `USER` / `PASSWORD` | Neo4j connection                 | `bolt://neo4j:7687` / `neo4j` / `test` |
| `MLFLOW_TRACKING_URI`             | MLflow server                    | `http://mlflow:5000`                   |
| `LLM_MODEL`                       | target model when provider wired | `gpt-4o-mini`                          |

> Operational guidance in [`docs/OPERATIONS.md`](docs/OPERATIONS.md) and observability in [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md).

---

## Screenshots

<p align="center">
  <!-- Replace paths with your real images in /docs/assets/ -->
  <img src="docs/assets/grafana-latency.png" width="31%" alt="Grafana latency" />
  <img src="docs/assets/jaeger-trace.png"  width="31%" alt="Jaeger trace" />
  <img src="docs/assets/api-docs.png"      width="31%" alt="FastAPI docs" />
</p>

---

## Troubleshooting / FAQ

**No metrics in Grafana?** Confirm Prometheus targets include `otel-collector:8889` and that the `otel-collector` service is healthy.
**No traces in Jaeger?** Ensure OTLP gRPC `4317` is reachable and sampling isn’t set to 0.
**/query returns 500?** Check container logs, env vars, and model/provider config (if enabled).
**Neo4j auth fails?** Default is `neo4j/test` (demo) — change in production and update `.env`.

---

## Compatibility Matrix

| Component        | Demo Default     | Notes                                   |
| ---------------- | ---------------- | --------------------------------------- |
| Python           | 3.11             | Typed; mypy/ruff/black configured       |
| Sentence-Transf. | all-MiniLM-L6-v2 | CPU‑friendly; swap for domain models    |
| FAISS            | faiss-cpu        | Switch to HNSW/vector DB > \~1M chunks  |
| Neo4j            | 5.x community    | Minimal schema; prod tune memory        |
| OTel Collector   | ≥ 0.106.0        | OTLP gRPC + Prometheus exporter         |
| MLflow           | 2.15.x           | SQLite demo; use object storage in prod |

---

## Roadmap

* Cross‑encoder re‑ranking; hybrid fusion (lexical+dense).
* Cost telemetry (tokens/\$) and cache metrics.
* AuthN/Z (OIDC), RBAC, per‑tenant metering.
* **RL Auto‑Tuner (PPO)** for automated config tuning.

---

## Contributing

* Run linters and tests locally:

```bash
make format && make lint && make type && make test
```

* PRs must pass CI (Ruff, Black, mypy, pytest). Keep docstrings **Google‑style** and maintain type hints.

---

## Maintainers & Support

* Maintainer: *Your Name* (@yourhandle) — contact via GitHub Issues.
* Bugs & feature requests: please open an issue with logs, versions, and steps to reproduce.

---

## License

**Apache‑2.0** — see `LICENSE`.

---

### GitHub “About” blurb (≤350 chars)

> Graph‑augmented RAG control plane (FastAPI, Neo4j+RDF, FAISS/BM25, RAGAS, OpenTelemetry → Prometheus/Grafana/Jaeger, MLflow). Observability, evaluation, GDPR guardrails, A/B testing. Roadmap: RL Auto‑Tuner (PPO) for cost↔quality↔latency.
