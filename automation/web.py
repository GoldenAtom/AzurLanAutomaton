"""LAN-only control panel; the bot remains independently managed by systemd."""
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
from automation.runtime import configure_logging

ROOT = Path(__file__).resolve().parents[1]
BIND = os.environ.get("AUTOMATON_WEB_BIND", "127.0.0.1")
PORT = int(os.environ.get("AUTOMATON_WEB_PORT", "8080"))
UNIT = "azurlane-bot.service"
ACTIONS = {"start", "stop", "restart"}


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Command failed")
    return result.stdout.strip()


def status():
    props = command("systemctl", "--user", "show", UNIT, "--property=ActiveState,SubState,MainPID,ExecMainStatus")
    info = dict(line.split("=", 1) for line in props.splitlines() if "=" in line)
    info["revision"] = command("git", "-C", str(ROOT), "rev-parse", "--short", "HEAD")
    info["mode"] = "idle (no game interaction)"
    info["logs"] = command("journalctl", "--user", "-u", UNIT, "-n", "35", "--no-pager", "-o", "short-iso")
    info["updates"] = command("systemctl", "--user", "show", "azurlane-update.timer", "--property=ActiveState")
    info["update_logs"] = command("journalctl", "--user", "-u", "azurlane-update.service", "-n", "12", "--no-pager", "-o", "short-iso")
    return info


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, content_type="application/json"):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        # Only the configured listener address may name this control endpoint.
        expected = "%s:%s" % self.server.server_address
        if self.headers.get("Host") != expected:
            self.reply(403, '{"error":"Unexpected host"}')
            return False
        return True

    def do_GET(self):
        if not self.valid_host():
            return
        if self.path == "/":
            self.reply(200, (ROOT / "automation" / "panel.html").read_text(), "text/html; charset=utf-8")
        elif self.path == "/api/status":
            try:
                self.reply(200, json.dumps(status()))
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                self.reply(503, json.dumps({"error": str(exc)}))
        else:
            self.reply(404, "{}")

    def do_POST(self):
        if not self.valid_host():
            return
        # JSON/custom header and exact Origin reject cross-site browser requests.
        expected = "http://" + self.headers.get("Host", "")
        if (self.headers.get("Origin") != expected or self.headers.get("X-Automaton-Control") != "1"
                or self.headers.get("Content-Type") != "application/json"):
            self.reply(403, '{"error":"Same-origin control required"}')
            return
        action = self.path.removeprefix("/api/")
        if action not in ACTIONS or self.path != "/api/" + action:
            self.reply(404, "{}")
            return
        try:
            command("systemctl", "--user", action, UNIT)
            logging.getLogger("control").info("Browser requested %s from %s", action, self.client_address[0])
            self.reply(200, '{"ok":true}')
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            self.reply(503, json.dumps({"error": str(exc)}))

    def log_message(self, fmt, *args):
        logging.getLogger("http").debug(fmt, *args)


def main():
    configure_logging("control")
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    logging.info("Browser controls listening on http://%s:%s", BIND, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
