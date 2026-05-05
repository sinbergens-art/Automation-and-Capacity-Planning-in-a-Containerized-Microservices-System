# SRE Shop — Microservices, Observability, IaC & Incident Simulation

End-to-end DevOps/SRE assignment combining **Assignment 4 (Incident Response)** and **Assignment 5 (Infrastructure as Code)**.
The system is a small e-commerce style application split into 5 FastAPI microservices, fronted by Nginx (which also acts as the API gateway), backed by PostgreSQL, observed through Prometheus + Grafana, and deployable to AWS via Terraform.

## Architecture

```
                              ┌─────────────┐
                              │   Browser   │
                              └──────┬──────┘
                                     │ :80
                              ┌──────▼──────┐
                              │   Nginx     │  ← static files + API gateway
                              │  (frontend) │
                              └──┬──┬──┬──┬─┘
                  ┌──────────────┘  │  │  └────────────┐
                  │                 │  │               │
        ┌─────────▼─────┐  ┌────────▼─┐│  ┌────────────▼──┐
        │ auth-service  │  │product-svc│  │ user-service  │
        └────────┬──────┘  └────────┬─┘│  └─────────┬────-┘
                 │                  │  │            │
                 │       ┌──────────▼──┴────┐       │
                 │       │ order-service    │       │
                 │       └──────────┬───────┘       │
                 │                  │               │
                 │       ┌──────────▼─────┐         │
                 └───────►   PostgreSQL   ◄─────────┘
                         └────────────────┘
                                ▲
        ┌──────────────────┐    │    ┌────────────────┐
        │ chat-service     ├────┘    │ Prometheus     │
        └──────────────────┘         │ + Grafana      │
                                     └────────────────┘
```

## Services

| Service              | Port (host)             | Purpose                        |
|----------------------|-------------------------|--------------------------------|
| **frontend** (Nginx) | 80                      | Static UI + reverse proxy      |
| auth-service         | 8001                    | Registration, login, JWT       |
| product-service      | 8002                    | Catalogue (read-heavy)         |
| order-service        | 8003                    | Orders (calls product-service) |
| user-service         | 8004                    | User profiles                  |
| chat-service         | 8005                    | User-to-user messages          |
| postgres             | 5432                    | Shared database                |
| prometheus           | 9090                    | Metrics scraping               |
| grafana              | 3001 (3000 in container)| Dashboards                     |

> **Note:** Locally we expose Grafana on `3001` because port `3000` was occupied on the dev machine.
> On the AWS deployment (Terraform), Grafana stays on the standard `3000` per the assignment spec.

## Project layout

```
sre-microservices/
├── docker-compose.yml          # main orchestration
├── .env                        # shared config (DB creds, JWT, Grafana admin)
├── services/
│   ├── auth-service/           # FastAPI + JWT + bcrypt
│   ├── product-service/        # FastAPI catalogue
│   ├── order-service/          # FastAPI + httpx (calls product-service)
│   ├── user-service/           # FastAPI profiles
│   └── chat-service/           # FastAPI messaging
├── frontend/                   # Nginx + index.html + app.js + style.css
├── monitoring/
│   ├── prometheus/             # prometheus.yml
│   └── grafana/                # provisioning + dashboards
├── postgres/                   # init.sql
├── terraform/                  # AWS IaC (Assignment 5)
├── reports/                    # incident report + postmortem (Assignment 4)
└── docs/                       # extra docs
```

## Quick start (local)

Prerequisites: Docker Desktop ≥ 4.30 (Compose V2 included).

```bash
# 1. Build all images and bring up the stack
docker compose build
docker compose up -d

# 2. Wait for everything to become healthy (~30-40s)
docker compose ps

# 3. Open
#    http://localhost            ← SRE Shop UI
#    http://localhost:9090       ← Prometheus
#    http://localhost:3001       ← Grafana (admin / admin)
```

Register a new user, browse the catalogue, place an order — everything lives end-to-end.

## Configuration

All runtime settings come from `.env` (12-factor):

```dotenv
DB_HOST=postgres
DB_PORT=5432
DB_NAME=appdb
DB_USER=appuser
DB_PASSWORD=apppass

JWT_SECRET=change-me-in-production-please
PRODUCT_SERVICE_URL=http://product-service:8000

GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
```

Changing one value rewires the whole stack — see `docker-compose.yml` for the wiring.

## Monitoring

Each FastAPI service exposes `/metrics` via [`prometheus-fastapi-instrumentator`](https://github.com/trallnag/prometheus-fastapi-instrumentator). Prometheus scrapes them every 10 s. Grafana auto-loads two things on first start:

* the Prometheus **datasource** (provisioned)
* the **SRE Shop — Microservices Overview** dashboard with 5 panels:
  1. Service UP / DOWN
  2. Request rate per service
  3. p95 latency per service
  4. 5xx errors per second per service
  5. Total requests by status code

These panels are what surface the simulated incident in Step 7.

## Tear down

```bash
docker compose down            # stop containers, keep data
docker compose down -v         # also remove volumes (Postgres, Prometheus, Grafana)
```

## Cloud deployment

For the AWS deployment via Terraform see [`terraform/README.md`](terraform/README.md).

## Reports (Assignment 4)

* [Incident Response Simulation](reports/incident-response.md)
* [Postmortem Analysis](reports/postmortem.md)

## How requirements map to deliverables

| Assignment item                      | Where in this repo                            |
|--------------------------------------|-----------------------------------------------|
| §3.1 Functional requirements         | `services/`, `frontend/`                      |
| §3.2 Non-functional (observability)  | `monitoring/`                                 |
| §6   Infrastructure as Code          | `terraform/`                                  |
| §7   Containerised deployment        | `docker-compose.yml`, `services/*/Dockerfile` |
| §8   Monitoring and observability    | `monitoring/prometheus`, `monitoring/grafana` |
| §9   Incident response simulation    | `reports/incident-response.md`                |
| §10  Postmortem analysis             | `reports/postmortem.md`                       |
| §11  Source code, configs, IaC, docs | this whole repo                               |

## Assignment 6 — Automation in SRE & Capacity Planning

Adds eight automation mechanisms and a quantitative capacity plan on top
of Assignments 4 and 5. See `docs/ASSIGNMENT-6-CHANGES.md` for the full
diff and `Assignment-6-Report.pdf` for the report.

```bash
# Pre-flight gate (catches Assignment-4-style regressions)
./scripts/validate_config.sh

# Start the stack — now includes Alertmanager + cAdvisor + webhook-sink
docker compose up -d --build

# Generate load
python3 scripts/load_test.py --scenario orders --users 50 --duration 30

# Scan logs for known failure patterns
./scripts/log_inspector.sh

# Horizontally scale the most resource-intensive service
docker compose up -d --scale order-service=3
```

UIs:
- App:           http://localhost
- Grafana:       http://localhost:3001
- Prometheus:    http://localhost:9090
- Alertmanager:  http://localhost:9093
- cAdvisor:      http://localhost:8081
- Webhook sink:  `docker compose logs -f webhook-sink`

# sre
