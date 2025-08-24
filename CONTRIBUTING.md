# Contributing to GraphRAG-Governor

Thanks for considering a contribution 🙌  
This guide covers setup, coding standards, testing, documentation, security, and the release flow. It’s designed so a new contributor can be productive in **under 15 minutes**.

---

## Quicklinks

- Project Overview → [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)  
- API Contract → [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md)  
- Observability → [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md)  
- Operations → [`docs/OPERATIONS.md`](docs/OPERATIONS.md)  
- Evaluation → [`docs/EVALUATION.md`](docs/EVALUATION.md)  
- RL Roadmap → [`docs/ROADMAP_RL_AUTOTUNER.md`](docs/ROADMAP_RL_AUTOTUNER.md)  
- Results Dossier → [`docs/RESULTS.md`](docs/RESULTS.md)  
- Security Policy → [`SECURITY.md`](SECURITY.md)

---

## TL;DR Dev Loop

```bash
# one-time
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # if present
pre-commit install

# run stack (API, Jaeger, Prometheus, Grafana, MLflow, Neo4j)
cp .env.example .env
docker compose up -d --build

# smoke tests
curl -s http://localhost:8000/health
curl -s -X POST "http://localhost:8000/query?variant=A&k=6" -H "Content-Type: application/json" -d '{"question":"Explain observability."}'

# quality gates
make format && make lint && make type && make test

# typical workflow
git checkout -b feat/my-change
# edit code...
git commit -m "feat(api): add X with OTel spans"
git push -u origin feat/my-change
# open PR with screenshots/trace IDs + rationale
