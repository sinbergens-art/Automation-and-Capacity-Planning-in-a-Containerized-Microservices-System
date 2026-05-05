# Incident Response Report — Order Service Database Connectivity Failure

**Project:** SRE Shop — Microservices System
**Assignment:** Assignment 4 — Incident Response Simulation
**Author:** Shynbergen
**Date:** 2026-05-01
**Incident ID:** INC-2026-001

---

## 1. Incident Summary

On 2026-05-01 at approximately **03:42:00 local time**, the **order-service** microservice became unable to connect to the PostgreSQL database. The service remained running at the process level — its `/metrics` endpoint continued to respond — but every business-critical request that touched the database returned **HTTP 503 Service Unavailable**, and the service's `/health` endpoint reported the database as unreachable.

The failure was introduced as part of a controlled chaos-engineering exercise (Assignment 4 § 9.2) by setting the `DB_HOST` environment variable in `docker-compose.yml` from `postgres` to `postgres-typo` — simulating a real-world configuration error such as a typo introduced during a deploy or a stale value in a secret manager.

The service was fully restored at **03:52:53 local time**. **Total incident duration: ~10 minutes 53 seconds.**


---

## 2. Impact Assessment

| Dimension | Impact |
|---|---|
| **Affected service** | order-service (1 of 5 backend microservices) |
| **User-facing symptom** | "My Orders" page returned **HTTP 500 / 502** in the browser. Users could not list their existing orders or place new orders. |
| **Unaffected services** | auth-service, product-service, user-service, chat-service, frontend, monitoring stack — all remained healthy throughout. |
| **Data loss** | **None.** The fault was a connectivity issue; no data was written or corrupted. Existing rows in `orders` and `order_items` tables were preserved (Postgres `pgdata` volume untouched). |
| **Estimated affected requests** | All `/orders` API calls during the incident window (~11 min). |
| **Estimated affected users** | All authenticated users who attempted to view or place orders during the window. |
| **Revenue impact** | Order creation was unavailable → 100% of new-order revenue lost during the window. Catalogue browsing and authentication continued to work, so users could still log in and browse products. |


---

## 3. Severity Classification

| Field | Value |
|---|---|
| **Severity** | **SEV-2 (Major)** |
| **Justification** | A core revenue-generating capability (order creation) was completely unavailable, but the failure was contained to one microservice — the rest of the platform kept serving traffic. No data loss occurred. Resolution required configuration change only, not code rollback. |
| **Comparable severity scale** | SEV-1 = full outage, SEV-2 = single critical feature down, SEV-3 = degraded non-critical, SEV-4 = cosmetic. |

---

## 4. Timeline of Events

All times are local (Asia/Almaty, UTC+5).

| Time | Δ from start | Event | Source |
|---|---|---|---|
| **03:42:00** | T+0:00 | **Incident START.** `DB_HOST` value in `docker-compose.yml` changed from `postgres` to `postgres-typo`. `docker compose up -d --force-recreate order-service` executed. | Manual action (chaos exercise) |
| 03:42:50 | T+0:50 | First failed `/health` request logged inside the order-service container — `503 Service Unavailable`. | Container logs |
| 03:43:00 | T+1:00 | **Detection.** "Service UP/DOWN" panel on the Grafana SRE Shop Overview dashboard turned the order-service tile to a **red DOWN** indicator. (Confirmed at the next 10 s scrape interval after the container's `/metrics` endpoint stopped reporting healthy DB connectivity.) | Grafana dashboard |
| 03:43:30 | T+1:30 | Engineer noticed Prometheus targets page showed order-service target probability dropping. Frontend reproduction of the bug — visited `My Orders` and observed `HTTP 500`. | Manual verification |
| 03:45:00 | T+3:00 | Started log analysis: `docker compose logs order-service --tail 30`. | Investigation |
| **03:48:39** | T+6:39 | **Root cause identified.** Log line `Health check failed: could not translate host name "postgres-typo" to address: Name or service not known` clearly pointed at a DNS resolution error inside the Docker network. | Container logs |
| 03:50:00 | T+8:00 | Mitigation plan formed: revert `DB_HOST` in `docker-compose.yml` and force-recreate the container. | Engineer decision |
| 03:51:00 | T+9:00 | `docker compose stop order-service` → traffic stopped reaching the broken instance. | Mitigation step 1 |
| 03:51:30 | T+9:30 | `docker-compose.yml` edited: `DB_HOST: postgres-typo` → `DB_HOST: ${DB_HOST}` (which resolves to `postgres` from `.env`). Saved. | Mitigation step 2 |
| 03:52:10 | T+10:10 | `docker compose up -d --force-recreate order-service` executed. | Mitigation step 3 |
| **03:52:53** | T+10:53 | **RESOLVED.** Container reported `(healthy)` in `docker compose ps`. `/health` returned `200 OK`. | Verification |
| 03:54:00 | T+12:00 | Validated via UI: placed a test order from the SRE Shop frontend — order id `#N` created successfully, listed in *My Orders*. | End-to-end check |

---

## 5. Root Cause Analysis

### 5.1 Direct cause

The order-service container could not resolve the hostname `postgres-typo`. Inside the Docker bridge network, hostnames are resolved against Docker's embedded DNS server (`127.0.0.11`); that server only knows about service names declared in `docker-compose.yml`. There is no service named `postgres-typo`, so DNS resolution failed and every database connection attempt aborted with:

```
could not translate host name "postgres-typo" to address: 
Name or service not known
```

### 5.2 Why the failure surfaced the way it did

* The `prometheus-fastapi-instrumentator` middleware exposes `/metrics` from in-process state and **does not** require database connectivity. That endpoint kept returning `200 OK` throughout the incident — meaning the standard Prometheus `up{}` metric *did not* drop to 0 until the container was eventually stopped.
* The `/health` endpoint, by contrast, opens a fresh DB connection on every call — so it returned `503` immediately, which is what surfaced first in container logs and the Grafana "Service UP/DOWN" panel.
* This is a classic case of *partial failure*: the process was alive, the metrics endpoint was alive, but the actual business-critical dependency was unreachable.

### 5.3 Underlying cause

The configuration surface for `DB_HOST` is a single environment variable propagated by `docker-compose.yml`. There is no validation step that would refuse to start the container with a hostname that does not resolve. A simple typo in this single string is therefore enough to break the service.

---

## 6. Mitigation Steps

The mitigation followed a deliberate "stop → fix → recreate → verify" sequence:

1. **Stop the affected container** to remove it from the load path:
   ```bash
   docker compose stop order-service
   ```
2. **Revert the configuration error** in `docker-compose.yml`:
   ```diff
   - DB_HOST: postgres-typo
   + DB_HOST: ${DB_HOST}
   ```
   (`${DB_HOST}` resolves to `postgres` via `.env`, restoring the correct service name.)
3. **Recreate the container** with the corrected configuration:
   ```bash
   docker compose up -d --force-recreate order-service
   ```
4. **Wait for the healthcheck loop to confirm health** (Docker `HEALTHCHECK` on the image runs every 15 s with 4 retries → up to 60 s).
5. **Verify** end-to-end:
   - `docker compose ps order-service` → `(healthy)`
   - `curl http://localhost:8003/health` → `200 OK`
   - Placing a test order from the frontend → `201 Created`


---

## 7. Resolution Confirmation

The incident is considered **fully resolved** when **all** of the following are true (verified at 03:54:00 local time):

| Signal | Expected | Actual |
|---|---|---|
| `docker compose ps order-service` | `Up (healthy)` | ✅ `Up (healthy)` |
| `curl -s http://localhost:8003/health` | `{"status":"ok","db_host":"postgres"}` | ✅ Confirmed |
| Grafana **Service UP/DOWN** panel | order-service tile **green UP** | ✅ Restored |
| Prometheus **/targets** page | `order-service` target shows **UP** | ✅ Restored |
| Frontend → **My Orders** | Lists existing orders, no errors | ✅ HTTP 200 |
| Frontend → **Place Order** flow | Creates a new order successfully | ✅ Order created |
| `docker compose logs order-service --tail 5` | No `[ERROR]` entries since recovery | ✅ Clean logs |


---

## 8. Supporting evidence (screenshots reference index)

| # | File | What it shows |
|---|---|---|
| 12 | `12-incident-before-grafana.png` | Pre-incident: all 5 services UP on the dashboard |
| 13 | `13-incident-before-prometheus.png` | Pre-incident: 6/6 Prometheus targets UP |
| 14 | `14-incident-before-frontend.png` | Pre-incident: frontend healthy |
| 15 | `15-incident-before-docker-ps.png` | Pre-incident: `docker compose ps` shows every container healthy |
| 16 | `16-incident-start-time.png` | Timestamp of the chaos injection |
| 17 | `17-incident-during-grafana.png` | During: order-service in red DOWN |
| 18 | `18-incident-during-prometheus.png` | During: order-service Prometheus target DOWN (after stop) |
| 19 | `19-incident-during-frontend-error.png` | During: frontend HTTP 500 on My Orders |
| 20 | `20-incident-during-docker.png` | During: `docker compose ps` shows order-service `(unhealthy)` |
| 21 | `21-incident-logs-error.png` | During: `[ERROR]` log line — "could not translate host name 'postgres-typo'" |
| 22 | `22-incident-rca-time.png` | RCA timestamp |
| 23 | `23-incident-recovery-time.png` | Resolution timestamp |
| 24 | `24-incident-after-grafana.png` | Post-incident: dashboard healthy again |
| 25 | `25-incident-after-prometheus.png` | Post-incident: targets all UP |
| 26 | `26-incident-after-frontend.png` | Post-incident: frontend works, new order created |
| 27 | `27-incident-after-docker.png` | Post-incident: every container `(healthy)` |
