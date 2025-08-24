# Operations — GraphRAG‑Governor ⚙️

> **Purpose:** A practical, end‑to‑end runbook for **non‑technical** and **technical** stakeholders. Covers environments, deployment, scaling, security, backups, SLOs, incident response, and FinOps.

---

## 1) Executive Summary (Non‑Technical) 🎯

**What Ops cares about.** We keep the service **available**, **fast**, **safe**, and **observable**. Dashboards show latency and errors; alerts trigger on issues; backups protect data.

**What you get.** One‑click local environment, clear health checks, and simple upgrade/rollback procedures. Costs are visible and tunable.

**Key promises.**

* **Reliability:** Health checks + alerts + tested rollbacks.
* **Performance:** Watch p95 latency and tune knobs (retrieval variant, top‑K, caches).
* **Security:** PII masking by default; UIs locked down in production.
* **Recoverability:** Neo4j/MLflow backups with restore playbooks.

---

## 2) Environments & Prerequisites 🧩

* **Local (dev):** Docker Engine/Desktop; Python 3.11 optional.
* **Prod‑like (single VM):** Docker + reverse proxy (Nginx/Traefik) + systemd units.
* **Kubernetes:** Ingress, Secrets, persistent volumes; OTel/Prom/Grafana via Helm.

**Ports (defaults)**

* API `8000`, Neo4j `7474/7687`, MLflow `5000`, Jaeger `16686`, Prometheus `9090`, Grafana `3000`, OTel gRPC `4317`.

---

## 3) Bootstrapping (Local) 🚀

```bash
cp .env.example .env
# Start full stack
docker compose up -d --build
# (Optional) Embed sample docs for dense retrieval demo
python scripts/bootstrap_index.py
# Smoke tests
curl -s http://localhost:8000/health | jq
curl -s -X POST "http://localhost:8000/query?variant=A&k=6" \
  -H 'Content-Type: application/json' \
  -d '{"question":"What privacy guarantees do you provide?"}' | jq
```

**Makefile shortcuts**

```bash
make install   # dependencies for local dev
make test      # pytest quick run
make up        # compose up -d --build
make down      # compose down -v
```

---

## 4) Configuration Management 🔧

* **Environment variables:** see `.env.example`. Configure `SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `NEO4J_*`, `MLFLOW_TRACKING_URI`.
* **Secrets:** never commit `.env`; use platform Secret Manager (K8s Secrets, AWS/GCP vaults). Rotate keys quarterly.
* **Config as code:** keep `prometheus.yml` and `otel-collector-config.yaml` under version control; review via PRs.

---

## 5) Deployment Topologies 🌐

### 5.1 Single VM (Docker Compose + Reverse Proxy)

* Terminate **TLS** at Nginx/Traefik.
* Expose **only** the API; keep MLflow/Neo4j/Prometheus/Grafana behind VPN or basic auth.
* Run services with `restart: unless-stopped`. Back up volumes (Neo4j, MLflow artifacts).

### 5.2 Kubernetes (Outline)

* **API:** Deployment + Service + Ingress (TLS). Set `readinessProbe` to `/health`.
* **Stateful:** Neo4j as **StatefulSet** with PersistentVolumeClaims.
* **Observability:** OTel Collector, Prometheus, Grafana via Helm charts.
* **Secrets:** OIDC/client keys in K8s Secrets; mount as env.

**HPA (example)**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: graphrag-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: graphrag-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 6) Networking & Security 🔐

* **TLS:** terminate at ingress; redirect HTTP→HTTPS.
* **CORS:** restrict `allow_origins` to trusted domains in production.
* **AuthN/Z:** add **OIDC SSO** at proxy or app; use **RBAC** to protect admin routes.
* **Ingress ACLs:** expose API only; block internal dashboards from the public Internet.
* **Rate limiting:** enforce request and payload size limits at the edge.
* **PII:** rely on built‑in masking; avoid raw payloads in traces/logs.

---

## 7) Scaling & Performance 🏎️

* **Gunicorn workers:** start with `workers = 2 * CPU + 1` (tune for I/O vs CPU bound).
* **Top‑K:** lower `k` for latency; raise for recall. Typical `k = 4–12`.
* **Retrieval variant:**

  * **A (BM25)** for keyword‑heavy queries.
  * **B (Dense/FAISS)** for semantic queries.
* **Caching (optional):** Redis for embeddings and answers; target 30–60% hit ratio.
* **Batching:** batch LLM or embedding calls when provider is enabled.

**Load test tips**

* Use k6/Locust; ramp to realistic QPS; watch `rag_latency_ms` p95/p99.
* Compare variant A/B under identical load; tune `k` and caches.

---

## 8) Observability Playbook 📈

* **Dashboards:** latency P50/P95, throughput, error rate, A/B comparison, evaluation trend (from MLflow).
* **Traces:** `http_query → retrieve → gather_contexts → generate`. Attribute `variant`, `k`, `latency_ms`.
* **Alerts (examples):** p95 > 500ms for 10m; error rate > 1% for 10m (see `docs/OBSERVABILITY.md`).
* **Log correlation:** propagate `traceparent` / `X‑Request‑ID` to logs.

---

## 9) Backups & Disaster Recovery 🧯

**Neo4j**

```bash
# Backup (stop writes first in prod)
docker exec -it <neo4j_container> neo4j-admin database dump neo4j --to-path=/backups
# Restore (new instance)
docker exec -it <neo4j_container> neo4j-admin database load neo4j --from-path=/backups --force
```

**MLflow**

* Artifacts: store on object storage (S3/GCS/Azure Blob) in prod; version runs.
* DB/backend: snapshot according to policy (daily/hourly).

**Prometheus/Jaeger**

* Configure retention windows; export snapshots before upgrades.

**RPO/RTO targets (examples)**

* **RPO:** ≤ 24h (daily backups).
* **RTO:** ≤ 2h (tested restore automation).

**Backup verification**

* Monthly restore tests in a staging environment; record timing and outcomes.

---

## 10) Release Management 🚢

* **Versioning:** Semantic versions (e.g., `v1.3.0`). Tag Docker images accordingly.
* **CI gates:** Ruff + Black + mypy + pytest must pass on PRs.
* **Staging → Prod:** Require A/B results on frozen validation slice; approver sign‑off.
* **Rollback:** keep N‑1 image; simple `docker compose` or K8s rollout undo.

---

## 11) Incident Response 🛎️

**Triage checklist**

* Is the API alive? `GET /health` (status 200).
* Are error rates rising? Grafana + Prometheus alerts.
* Trace a failing request in Jaeger; identify slow span.
* Check Neo4j/MLflow container logs; verify disk/CPU.

**Common issues & fixes**

* **High latency:** lower `k`, scale API, pre‑warm caches, inspect retriever.
* **5xx errors:** check provider quotas/timeouts (if LLM enabled); look for bad env vars.
* **No telemetry:** validate OTel Collector/ports; fall back to no‑op is expected.

**Post‑mortem**

* Document root cause, impact window, action items; link dashboards and traces.

---

## 12) Data Retention & Compliance 🗄️

* **PII:** masked by default; log redaction policies enforced.
* **Telemetry:** set Prometheus/Jaeger retention per policy (e.g., 7–30 days).
* **MLflow:** keep experiments ≥ 90 days (or per domain policy); archive old runs.
* **Access:** restrict dashboard UIs; SSO where possible.

---

## 13) FinOps 💸

* **Cost telemetry:** add token counters and emit `rag_cost_usd` (see roadmap).
* **Right‑size:** scale to zero off‑hours (dev); use HPA in prod.
* **Cache first:** aggressive caching can reduce cost/latency 30–60%.
* **Storage:** move MLflow artifacts to cheap object storage; set lifecycle rules.

---

## 14) Maintenance Tasks 🧹

* Rotate keys/secrets quarterly.
* Prune Docker images/volumes; upgrade base image monthly.
* Rebuild FAISS indexes after large corpus changes.
* Validate backups; test restore monthly.
* Review alerts for noise; tune thresholds quarterly.

---

## 15) Checklists ✅

**Go‑Live**

* [ ] TLS enabled; API behind ingress
* [ ] AuthN/Z configured (OIDC + RBAC)
* [ ] Dashboards and alerts verified
* [ ] Backups running & tested
* [ ] Error budget & SLOs agreed

**Upgrade**

* [ ] Release notes reviewed
* [ ] Backup/snapshot taken
* [ ] Deploy to staging; A/B checks pass
* [ ] Promote to prod; monitor p95 & errors
* [ ] Rollback plan ready

**DR Drill**

* [ ] Restore Neo4j snapshot in staging
* [ ] Restore MLflow artifacts/DB
* [ ] Verify API runs end‑to‑end

---

## 16) Appendices 📎

**Default demo creds** (change in prod!)

* Neo4j: `neo4j/test`

**References**

* `docs/OBSERVABILITY.md` — metrics, tracing, alerts
* `docs/SECURITY_GDPR.md` — security & compliance
* `docs/ARCHITECTURE.md` — component model

