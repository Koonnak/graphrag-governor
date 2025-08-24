# Changelog

All notable changes to this project are documented here. The format follows **Keep a Changelog** conventions and **Semantic Versioning**.

**Types used:**  
**Added** – new features • **Changed** – behavior changes • **Deprecated** – soon-to-be removed • **Removed** – now gone • **Fixed** – bug fixes • **Security** – vulnerability notes • **Docs** – documentation • **Ops** – operational guidance • **CI** – build/test/release • **Perf** – performance

---

## [Unreleased]

### Added
- **Results dossier pipeline**: `scripts/quick_eval.py` (A/B latency probe) and `scripts/mk_results_md.py` (auto-generates `docs/RESULTS.md` + latency chart).
- **Evidence pack guidance**: README “Proof of Execution” section linking to `docs/assets/` (API docs, Jaeger trace, Grafana p95).

### Changed
- README: add TOC, FAQ, screenshots, compatibility matrix, and real CI badge targets.
- Docs: cross-link Architecture ↔ Observability ↔ Operations for faster onboarding.

### Fixed
- Avoid broken links when optional docs are removed (README guards for missing pages).
- Docker Compose: minor health-check tune-ups in comments.

### CI
- (Planned) GHCR image publishing on tags `v*`.
- (Planned) Coverage reporting and upload (pytest + coverage).

### Security
- (Planned) `SECURITY.md` + private advisory workflow.

### Ops
- (Planned) Exported Grafana dashboards (`docs/dashboards/*.json`) + import instructions.

> **Maintainer note:** When cutting the next release, move items from **Unreleased** into the new version and create a git tag.

---

## [0.1.0] – 2025-08-24 — Initial public release

### Added
- **API (FastAPI)**
  - `/query?variant=A|B&k=<int>` — A/B retrieval with top-K control.
  - `/health` — liveness/ready probe for reverse proxies and K8s.
  - OpenAPI docs at `/docs` for contract clarity.

- **Retrieval**
  - **Variant A (BM25)**: lexical scoring (cpu-friendly baseline).
  - **Variant B (Dense/FAISS)**: Sentence-Transformers embeddings + FAISS IP index.
  - Deterministic seeding & simple in-memory demo corpus (`data/sample_docs/`).

- **Guardrails**
  - Pre/post **PII masking** (redact secrets & personal data at boundaries).
  - Minimal policy hooks for future LLM-as-judge integration.

- **Observability**
  - **OpenTelemetry** SDK wiring; spans: `http_query → retrieve → gather_contexts → generate`.
  - **OTel Collector** config → **Jaeger** (traces) + **Prometheus** (metrics).
  - **Metrics**: `rag_requests_total` (Counter), `rag_latency_ms` (Histogram).
  - **Grafana** ready (Prometheus datasource), with example p95 query in docs.

- **Evaluation (foundations)**
  - Evaluation docs outlining **RAGAS + MLflow** harness (provider-agnostic).
  - Seed instructions for local slices and reproducible runs.

- **Knowledge Graph readiness**
  - Minimal Neo4j wiring expectations (schema sketch for `(:Document)`).
  - RDF export mention for triple-store interop (roadmap).

- **Docs (non-tech + tech)**
  - `docs/ARCHITECTURE.md` — executive summary + deep component breakdown.
  - `docs/API_REFERENCE.md` — non-tech overview + HTTP contract.
  - `docs/OBSERVABILITY.md` — metrics, traces, dashboards, alert templates.
  - `docs/OPERATIONS.md` — environments, deployment, scaling, DR, checklists.
  - `docs/EVALUATION.md` — methodology & RAGAS harness plan.
  - `docs/ROADMAP_RL_AUTOTUNER.md` — MDP, PPO, safety gates, promotion policy.

- **DevEx & Ops**
  - **Docker Compose** one-click stack (API, Jaeger, Prometheus, Grafana, MLflow, Neo4j).
  - `Makefile` (format/lint/type/test/up/down) for fast local workflows.
  - `.env.example` with sane defaults (never commit secrets).
  - `prometheus.yml`, `otel-collector-config.yaml` checked in (config-as-code).

- **Quality gates**
  - `pyproject.toml` + `requirements.txt` with pinned, narrow ranges.
  - **Pre-commit** (`ruff`, `black`) config.
  - **CI workflow** (`.github/workflows/ci.yml`) for lint/type/test.

- **Testing**
  - `tests/` scaffolding with a minimal health + A/B contract smoke test (example).

- **Licensing**
  - `LICENSE` (Apache-2.0).

### Changed
- README elevated to **flagship**: TOC, Quickstart, docs map, screenshots, FAQ, compatibility matrix, roadmap, contributing, maintainers.

### Fixed
- N/A (first release).

### Security
- Default **demo creds** documented and flagged to change in production.
- Guidance to restrict dashboards (Grafana/Jaeger/MLflow) to private networks.

### Ops
- Step-by-step runbook for local bootstrap and smoke checks (`curl /health`, `/query`).

### Upgrade notes
- N/A (first release). Consumers should copy `.env.example` → `.env` and use `docker compose up -d --build`.

---

## Release process (for maintainers)

1. Ensure **CI is green** on `main`.
2. Update **Unreleased** → new version section; set date `YYYY-MM-DD`.
3. Bump version strings if you publish images or packages.
4. Tag and push:
   ```bash
   git tag vX.Y.Z -a -m "Release vX.Y.Z"
   git push --tags
