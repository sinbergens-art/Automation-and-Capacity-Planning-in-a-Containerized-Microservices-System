# Assignment 6 — What Changed

A flat list of every file added or modified for Assignment 6. Use this as
the diff cover when reviewing the submission.

## New files

| File                                         | Purpose                                              |
| -------------------------------------------- | ---------------------------------------------------- |
| `monitoring/prometheus/alert_rules.yml`      | Eight Prometheus alert rules in 5 groups             |
| `monitoring/alertmanager/alertmanager.yml`   | Alertmanager routing + receivers                     |
| `monitoring/webhook-sink/sink.py`            | Tiny webhook receiver (stand-in for Slack/PagerDuty) |
| `scripts/validate_config.sh`                 | Pre-flight env / compose / DNS validation            |
| `scripts/log_inspector.sh`                   | Pattern-based log inspection automation              |
| `scripts/load_test.py`                       | Async load generator (mixed/orders/health)           |
| `docs/RUNBOOK.md`                            | One-page incident playbook                           |
| `docs/ASSIGNMENT-6-CHANGES.md`               | This file                                            |
| `Assignment-6-Report.pdf` *(top-level)*      | Final assignment report                              |

## Modified files

| File                                  | What changed                                                                         |
| ------------------------------------- | ------------------------------------------------------------------------------------ |
| `docker-compose.yml`                  | Resource limits, Alertmanager + cAdvisor + webhook-sink, scale-friendly order-service|
| `monitoring/prometheus/prometheus.yml`| `alerting` block, `rule_files`, cAdvisor scrape job                                  |
| `frontend/nginx.conf`                 | Variable-based proxy_pass + proxy_next_upstream for round-robin LB                   |
| `terraform/variables.tf`              | `instance_type` validation, `service_replicas`, `root_volume_size_gb`                |
| `terraform/main.tf`                   | `templatefile()` for user_data, Alertmanager ingress on :9093, richer tags          |
| `terraform/outputs.tf`                | `alertmanager_url`, `instance_size`, `service_replicas` outputs                      |
| `terraform/user_data.sh`              | Now a Terraform template; renders `${service_replicas}` into /etc/sre-shop.env       |

## Action items closed (from the Assignment-4 postmortem)

| #  | Action                                  | Where                                            |
| -- | --------------------------------------- | ------------------------------------------------ |
| 1  | Alert on /health 5xx > 60 s             | `alert_rules.yml` — HighErrorRate, AnyHTTP5xxErrors |
| 2  | Multi-signal up/5xx alert               | `alert_rules.yml` — ServiceDown, AllBackendServicesDown |
| 3  | CI `docker compose config -q`           | `scripts/validate_config.sh` — Check 2/5         |
| 4  | Pre-flight DB_HOST resolution           | `scripts/validate_config.sh` — Check 3/5         |
| 5  | Connection retry with backoff           | Already in services/*/main.py (`get_db()`)       |
| 6  | One-page incident playbook              | `docs/RUNBOOK.md`                                |
| 7  | Pydantic typed config                   | Open — out of scope for A6                       |
| 8  | Quarterly chaos drill                   | Process — re-run `load_test.py` + `log_inspector.sh` |
