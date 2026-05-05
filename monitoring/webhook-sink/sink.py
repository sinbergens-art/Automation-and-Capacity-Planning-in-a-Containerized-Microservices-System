"""
Tiny webhook-sink — Assignment 6.

Listens on :8080 and prints every incoming Alertmanager webhook to stdout.
This stands in for a real Slack / PagerDuty / Opsgenie integration so we can
demonstrate the full alerting pipeline (Prometheus -> Alertmanager -> sink)
end to end without leaking any real credentials.

Run inside Docker (see docker-compose.yml `webhook-sink` service):
    docker compose logs -f webhook-sink
will show every alert as JSON, one per request.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] webhook-sink: %(message)s",
)
log = logging.getLogger("webhook-sink")


class AlertHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}

        route = self.path.lstrip("/")
        for alert in payload.get("alerts", []):
            status = alert.get("status", "?")
            labels = alert.get("labels", {})
            ann = alert.get("annotations", {})
            log.info(
                "[route=%s] %s | %s | service=%s | severity=%s | %s",
                route,
                datetime.utcnow().strftime("%H:%M:%S"),
                status.upper(),
                labels.get("service", labels.get("job", "n/a")),
                labels.get("severity", "n/a"),
                ann.get("summary", labels.get("alertname", "alert")),
            )

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"received":true}')

    def log_message(self, format: str, *args) -> None:  
        pass


def main() -> None:
    addr = ("0.0.0.0", 8080)
    log.info("Starting webhook-sink on http://%s:%s", *addr)
    HTTPServer(addr, AlertHandler).serve_forever()


if __name__ == "__main__":
    main()
