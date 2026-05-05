# Postmortem Analysis — Order Service Database Connectivity Failure (INC-2026-001)

**Project:** SRE Shop
**Incident ID:** INC-2026-001 (companion to *Incident Response Report*)
**Date of postmortem:** 2026-05-01
**Author:** Shynbergen
**Status:** Closed
**Severity:** SEV-2 (Major)
**Total duration:** 10 min 53 s

---

## 1. Incident Overview

A controlled chaos-engineering exercise injected an invalid `DB_HOST` value (`postgres-typo` instead of `postgres`) into the **order-service** container's environment. The resulting DNS resolution failure inside the Docker network rendered every database-dependent endpoint of the order-service inoperative for approximately **11 minutes**, while leaving the surrounding microservices and the rest of the platform intact.

The fault was detected within ~1 minute via the Grafana SRE Shop Overview dashboard, root-caused within ~7 minutes via container log inspection, and fully resolved within ~11 minutes via a configuration rollback and a `docker compose up -d --force-recreate` of the affected container.


---

## 2. Customer Impact

| Aspect | Detail |
|---|---|
| Affected feature | **Order management** — listing previous orders and placing new orders. |
| Affected users | All authenticated users who attempted to use *My Orders* during the window. |
| Estimated request failures | 100% of `GET /orders` and `POST /orders` calls during the ~11 min window. |
| Visible symptom | UI showed *"❌ HTTP 500"* on the *My Orders* tab and on checkout. |
| Workaround during incident | None available to end users. (Browsing and authentication continued to function.) |
| Data integrity | **No data loss.** Postgres `orders` and `order_items` rows that existed before the incident were preserved. No partial writes occurred (transactions failed early at the connection step). |

Although the simulation ran in a lab environment with no external customers, the impact pattern is representative of a production outage: a single-feature degradation rather than a full platform outage.

---

## 3. Root Cause Analysis

### 3.1 Five Whys

1. **Why** did *My Orders* return HTTP 500?
   The frontend received an upstream error from order-service.
2. **Why** did order-service return errors?
   It could not connect to its database.
3. **Why** could it not connect?
   The hostname `postgres-typo` did not resolve to any IP address inside the Docker network.
4. **Why** was the hostname wrong?
   The `DB_HOST` value in `docker-compose.yml` was edited from `postgres` to `postgres-typo` and not validated before the container was recreated.
5. **Why** was an invalid value allowed to ship?
   There is no pre-flight validation step that resolves the DB hostname before starting the container, no CI/lint check on `docker-compose.yml` against `.env`, and no canary stage that would have caught the failure on a single instance before promoting it.

### 3.2 Contributing factors

| Factor | Description |
|---|---|
| **Single-string blast radius** | `DB_HOST` is one string in one file with no schema validation; a one-character typo is enough to disable the service. |
| **Soft-failure invisibility on Prometheus `up`** | `/metrics` kept returning 200, so the standard Prometheus `up{}` metric did not flip until the container was explicitly stopped. The "Service UP/DOWN" panel was driven by `up{}`, which delayed the *Prometheus-level* signal. |
| **No automated alerts** | Detection relied on a human operator visually noticing the dashboard. There is no alerting rule that pages on `/health` returning 5xx. |
| **No deploy gate** | The container restarted as soon as compose was told to do so; there was no smoke-test or healthcheck-gated promotion. |

### 3.3 What worked well

* **Per-service `/health` endpoints** that actually exercise the DB connection — these correctly returned 503 within the first scrape interval.
* **Structured logs** (`[ERROR] Health check failed: could not translate host name "postgres-typo"...`) made root cause obvious within seconds of opening the log.
* **Idempotent infrastructure** (`docker compose up -d --force-recreate order-service`) — restoring the service was a one-command operation with no manual cleanup.
* **Per-service Docker `HEALTHCHECK` directive** in the Dockerfile — `docker compose ps` immediately surfaced the `(unhealthy)` state.
* **Fault isolation between microservices** — auth, product, user, chat services and the frontend kept serving traffic throughout. The blast radius was limited to the one feature that depended on the broken service.

---

## 4. Detection and Response Evaluation

| Phase | Time taken | Evaluation |
|---|---|---|
| **Time to detect** (TTD) | ~1 minute | ✅ Fast — Grafana refresh interval (10 s) + Prometheus scrape interval (10 s) means the dashboard reflects new state within ~20 s after the failure mode begins emitting 5xx. The remaining ~40 s was the human operator's eyes-on time. |
| **Time to identify root cause** (TTR-RCA) | ~7 minutes | ⚠️ Slower than ideal — improved by `[ERROR]` log being explicit, but slowed by the absence of an alert that would have led the operator straight to the offending service. |
| **Time to mitigate** (TTM) | ~4 minutes | ✅ Acceptable — the fix was a single line revert + a `force-recreate`. |
| **Time to fully resolve** (TTR) | ~11 minutes | ✅ Acceptable for SEV-2 in a single-engineer operation. Industry SLO targets are typically 30 min for SEV-2. |

### Strengths
- Health endpoint design that actually checks the dependency — not a "200 if process running" stub.
- Logs were searchable and unambiguous (`grep ERROR` was sufficient).
- Recovery procedure was scriptable and deterministic.

### Weaknesses
- No alerting → relied on operator already watching the dashboard.
- The `up{}` metric did not reflect the partial failure — only the `/health` endpoint did. A multi-signal alert (e.g., `up == 0 OR rate(http_requests_total{job="order-service",status=~"5.."}[1m]) > 0`) would have caught it sooner.
- No deployment validation step — broken config went straight to "running" with no smoke test.

---

## 5. Resolution Summary

The fix consisted of three actions, executed in order:

1. **Stop** the broken instance to take it out of the request path:
   ```bash
   docker compose stop order-service
   ```
2. **Revert** `DB_HOST` in `docker-compose.yml` to its correct value `${DB_HOST}` (which resolves to `postgres` from `.env`).
3. **Recreate** the container so the corrected environment is applied:
   ```bash
   docker compose up -d --force-recreate order-service
   ```

Health was confirmed via `docker compose ps` (status `healthy`), `/health` endpoint returning 200, the Grafana Service UP/DOWN panel turning green, and a successful end-to-end order placement from the frontend.

**No code changes were required.** This was purely a configuration regression.

---

## 6. Lessons Learned

1. **Health endpoints must exercise the actual dependencies.** A `/health` that simply returns "200 OK" because the process is alive would have hidden this incident from monitoring entirely. Our endpoint opens a fresh DB connection on every call — that single design decision provided the strongest signal during the outage.

2. **`up{}` alone is insufficient for partial failures.** The classic `up{job="X"} == 0` rule only fires when the metrics endpoint itself goes down. Real services can be "up" by Prometheus but unable to do their job. Multi-signal alerts (`up`, `5xx rate`, `dependency latency`) are necessary.

3. **Configuration is code — and should be reviewed and validated like code.** A single-character typo in `docker-compose.yml` was sufficient to break a production-shaped feature. CI checks (`docker compose config` schema validation, hostname-resolution smoke tests) should be a gate, not an afterthought.

4. **Dashboards beat log-trawling for first-pass detection.** The operator went from "something feels off" to "order-service is DOWN" in ~30 seconds purely by looking at a single panel. Logs were essential for RCA but only after the dashboard pointed to the right service.

5. **Microservices buy you blast-radius isolation — but only if dependencies are isolated too.** The four other backend services kept running because they didn't share the broken config. Had `DB_HOST` been a global setting affecting all services, this would have been a SEV-1.

6. **Idempotent recovery commands save real minutes.** `docker compose up -d --force-recreate <svc>` is a one-shot remediation that is safe to re-run. Building infrastructure that can be rolled back with one command turns a stressful incident into a routine fix.

---

## 7. Action Items

Action items follow the assignment's four required dimensions (§ 10.3): address weaknesses, improve monitoring/alerting, enhance deployment reliability, and reduce future risk. Each item has an owner (placeholder) and a target completion date.

| # | Action | Type | Priority | Owner | Target |
|---|---|---|---|---|---|
| 1 | **Add a Prometheus alert rule** that fires when the order-service `/health` endpoint returns 5xx for more than 60 seconds. Wire it to a Grafana notification channel (email or Slack webhook). | Monitoring | High | Platform Eng | +1 week |
| 2 | **Add a multi-signal Grafana alert** — `up == 0` OR `rate(http_requests_total{status=~"5.."}[1m]) > 0` — so partial failures trigger pages even when `/metrics` keeps responding. | Monitoring | High | Platform Eng | +1 week |
| 3 | **Add a CI check** that runs `docker compose config -q` on every PR that touches `docker-compose.yml` or `.env` to catch syntax errors and unresolved variables. | Deployment | High | DevOps | +2 weeks |
| 4 | **Add a config-validation pre-flight script** that, before `docker compose up`, attempts to resolve `DB_HOST` from inside a transient container and aborts the deploy if resolution fails. | Deployment | Med | DevOps | +2 weeks |
| 5 | **Implement a connection retry with capped backoff and circuit breaker** in order-service so a transient DNS hiccup does not immediately turn into 503s. | Reliability | Med | Backend Eng | +3 weeks |
| 6 | **Document the incident playbook**: a one-page runbook for the engineer on call, capturing detection signals, diagnostic commands, mitigation steps, and verification checks (using this incident as the worked example). | Process | Med | SRE Lead | +2 weeks |
| 7 | **Promote `DB_HOST` and similar critical settings to a typed configuration system** (e.g., a Pydantic settings model) so invalid values are caught at startup rather than at first DB call. | Reliability | Low | Backend Eng | +6 weeks |
| 8 | **Run a quarterly chaos-engineering drill** that re-introduces this exact failure (or a variant — wrong port, wrong password, dropped network) and times the response. Use the metrics to track TTD/TTM trends across drills. | Process | Low | SRE Lead | Quarterly |

---

## 8. Closing notes

This incident, although deliberately injected, behaved exactly like a real production configuration regression — the kind that is one PR review away from shipping in any team. The system's recovery characteristics were good (fast detection on the dashboard, clean logs, single-command remediation), but the absence of automated alerting and CI-side configuration validation are real gaps that the action items above are intended to close.

The SRE Shop platform passed its first chaos test: one microservice fell, the rest kept serving, the data was preserved, and the recovery procedure was reproducible.

— *End of postmortem.*
