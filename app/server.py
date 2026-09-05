"""Tiny JSON HTTP server for the demo app. Standard library only.

Environment:
  PORT      default 8080 (cloud paths expect 8080)
  HOST      default 127.0.0.1; containers set 0.0.0.0
  MODE      auto (default), durable, stateless
  DATA_DIR  default ./data; ignored in stateless mode
"""

import json
import os
import sqlite3
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import SERVICE_NAME, __version__, store

MAX_BODY = 1_000_000


def resolve_mode(data_dir):
    mode = os.environ.get("MODE", "auto").strip().lower()
    if mode == "stateless":
        return "stateless"
    if mode == "durable":
        return "durable"
    if mode != "auto":
        raise SystemExit("unknown MODE=%r; use auto, durable or stateless" % mode)
    try:
        os.makedirs(data_dir, exist_ok=True)
        probe = os.path.join(data_dir, ".write-probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
        return "durable"
    except OSError:
        return "stateless"


def build_store():
    data_dir = os.path.abspath(os.environ.get("DATA_DIR", "./data"))
    mode = resolve_mode(data_dir)
    if mode == "durable":
        return store.Store(os.path.join(data_dir, "app.db")), mode, data_dir
    return store.Store(None), "stateless", data_dir


class AppHTTPServer(ThreadingHTTPServer):
    """Threading HTTP server that carries the shared store."""

    store = None

    def __init__(self, st, host, port):
        super().__init__((host, port), Handler)
        self.store = st


def create_server(st, host, port):
    return AppHTTPServer(st, host, port)


class Handler(BaseHTTPRequestHandler):
    server_version = "deployment-starter/%s" % __version__

    def _reply(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b""
        if not raw:
            raise ValueError("empty request body")
        parsed = json.loads(raw.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("request body must be a JSON object")
        return parsed

    def _do_get(self, path):
        st = self.server.store
        if path == "/":
            return 200, {
                "service": SERVICE_NAME,
                "version": __version__,
                "endpoints": {
                    "GET /health": "status, mode, storage",
                    "GET /api/items": "list inventory items",
                    "POST /api/items": "create item (name, price_cents, stock)",
                    "GET /api/orders": "list orders",
                    "POST /api/orders": "create order (customer_name, item_id, quantity)",
                    "GET /api/summary": "items, orders, revenue_cents, low_stock",
                },
            }
        if path == "/health":
            body = st.health()
            body.update(
                {"service": SERVICE_NAME, "version": __version__}
            )
            return 200, body
        if path == "/api/items":
            return 200, st.list_items()
        if path == "/api/orders":
            return 200, st.list_orders()
        if path == "/api/summary":
            return 200, st.summary()
        return 404, {"error": "not found"}

    def _do_post(self, path):
        st = self.server.store
        data = self._read_json()
        if path == "/api/items":
            item_id = st.add_item(
                data.get("name"), data.get("price_cents"), data.get("stock")
            )
            row = [i for i in st.list_items() if i["id"] == item_id][0]
            return 201, row
        if path == "/api/orders":
            order_id = st.add_order(
                data.get("customer_name"), data.get("item_id"), data.get("quantity")
            )
            row = [o for o in st.list_orders() if o["id"] == order_id][0]
            return 201, row
        return 404, {"error": "not found"}

    def _handle(self, method):
        path = urlparse(self.path).path
        try:
            if method == "GET":
                code, body = self._do_get(path)
            else:
                code, body = self._do_post(path)
            self._reply(code, body)
        except (ValueError, KeyError, TypeError) as exc:
            self._reply(400, {"error": str(exc)})
        except sqlite3.IntegrityError as exc:
            self._reply(409, {"error": str(exc)})
        except sqlite3.Error as exc:
            self._reply(500, {"error": "database error"})
            traceback.print_exc(file=sys.stderr)
        except Exception:
            self._reply(500, {"error": "internal error"})
            traceback.print_exc(file=sys.stderr)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def log_message(self, format, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), format % args))


def main():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    st, mode, data_dir = build_store()
    httpd = create_server(st, host, port)
    print(
        "deployment-starter %s listening on http://%s:%d mode=%s data_dir=%s"
        % (__version__, host, port, mode, data_dir),
        file=sys.stderr,
    )
    print(
        "data survives restarts only in durable mode with a persistent volume",
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        st.close()


if __name__ == "__main__":
    main()
