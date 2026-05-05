# SRE Shop — Incident Runbook

This is the one-page incident playbook referenced from Prometheus alerts.
It captures the detection signals, diagnostic commands, mitigation steps,
and verification gates for the failure modes we have actually seen in
this system. Last updated: Assignment 6.

---

## Quick triage (first 60 seconds)

```bash
# Where am I?
docker compose ps

# Which targets are scraping?
open http://localhost:9090/targets

# Are alerts firing?
open http://localhost:9090/alerts
open http://localhost:9093          # Alertmanager UI

# What does Grafana see?
open http://localhost:3001/d/sre-shop-overview
```

If `docker compose ps` shows `(unhealthy)` or `Restarting` — go to
[Service Down / Crash Loop](#service-down).

If Grafana shows 5xx without UP/DOWN flicker — go to
[Partial Failure](#partial-failure).

---

## <a name="service-down"></a>1. Service Down (alert: `ServiceDown`)

**Signal**: `up{job="X-service"} == 0` for >= 1 min.

**Diagnose**:
```bash
docker compose ps X-service
docker compose logs X-service --tail 50 --no-color
./scripts/log_inspector.sh X-service
```

**Common root causes**:

| Symptom in logs                                  | Cause                                                                        |
| ------------------------------------------------ | ---------------------------------------------------------------------------- |
| `could not translate host name "..."`            | Bad DB_HOST (Assignment-4 incident family) — run `validate_config.sh`        |
| `Connection refused on 127.0.0.1:5432`           | Postgres container down                                                      |
| `Killed` / OOM                                   | Container exceeded memory limit — bump `deploy.resources.limits.memory`      |
| Repeating `Starting...`                          | Crash on startup — read the LAST 5 lines of logs                             |

**Mitigate**:
```bash
# 1. Pull the broken instance out of the load path
docker compose stop X-service

# 2. Fix the underlying cause (typically: edit .env or docker-compose.yml)

# 3. Force-recreate
docker compose up -d --force-recreate X-service

# 4. Verify
docker compose ps X-service                # (healthy)
curl -fsS http://localhost:8003/health     # 200 OK
```

---

## <a name="partial-failure"></a>2. Partial Failure (alert: `HighErrorRate`)

**Signal**: 5xx ratio > 5 % over 2 min, but `up{}` stays at 1.
This is the *Assignment-4-style* failure — process up, dependency broken.

**Diagnose**:
```bash
# 1) Are 5xx coming from a single endpoint?
curl -s http://localhost:9090/api/v1/query?query='topk(5, rate(http_requests_total{status=~"5.."}[5m]))' \
  | jq .

# 2) Inspect logs for the noisy service
./scripts/log_inspector.sh order-service
```

**Mitigate**: Same as above — stop / fix / recreate / verify.

---

## 3. High Latency (alert: `HighRequestLatency`)

**Signal**: p95 latency > 1 s over 5 min.

**First check**: Is it just one service or all of them?
- One service ⇒ that service is overloaded; consider horizontal scaling
- All services ⇒ the database or the host is the bottleneck

**Mitigate (one service overloaded)**:
```bash
# Add 2 more replicas of order-service
docker compose up -d --scale order-service=3
```

**Mitigate (DB bottleneck)**:
- Raise the EC2 instance size in `terraform.tfvars` (`t3.medium` → `t3.large`)
- Run `terraform apply`
- Re-deploy the stack on the new host

---

## 4. Container Restart Loop (alert: `TargetFlapping`)

**Signal**: `up{}` flips at least 3 times in 10 min.

Almost always one of: bad image, bad env var, depends_on race condition, or
OOM. Use the same diagnose / mitigate flow as Service Down.

---

## 5. Alertmanager Itself Is Down

If you cannot reach `http://localhost:9093`, alerts are firing into the void.

```bash
docker compose logs alertmanager --tail 50
docker compose restart alertmanager
```

---

## Verification gate

Before declaring an incident resolved:

1. `docker compose ps` shows the affected service `(healthy)`
2. `curl -fsS http://localhost:<port>/health` returns 200
3. Grafana panels for that service are green for 5 min
4. Alertmanager `Active alerts` page is empty
5. Run `./scripts/log_inspector.sh` — must print "OK"

Then echo the resolved-at timestamp into the incident channel:
```bash
echo "Incident RESOLVED: $(date '+%Y-%m-%d %H:%M:%S')"
```
