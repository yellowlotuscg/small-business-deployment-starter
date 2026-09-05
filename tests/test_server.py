"""HTTP layer tests: real server thread, real requests, JSON contract."""
import json
import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import __version__, server, store


class ServerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = store.Store(os.path.join(self._tmp.name, "http.db"))
        self.httpd = server.create_server(self.store, "127.0.0.1", 0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)
        self.store.close()
        self._tmp.cleanup()

    def request(self, method, path, payload=None):
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except HTTPError as err:
            return err.code, json.loads(err.read().decode("utf-8"))


class TestHealth(ServerCase):
    def test_health_returns_expected_json(self):
        status, body = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["service"], "deployment-starter")
        self.assertEqual(body["mode"], "durable")
        self.assertEqual(body["storage"], "file")
        self.assertEqual(body["version"], __version__)
        self.assertTrue(body["writable"])

    def test_stateless_memory_store_reports_mode(self):
        mem_store = store.Store(None)
        httpd = server.create_server(mem_store, "127.0.0.1", 0)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            port = httpd.server_address[1]
            with urlopen("http://127.0.0.1:%d/health" % port, timeout=5) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body["mode"], "stateless")
            self.assertEqual(body["storage"], "memory")
        finally:
            httpd.shutdown()
            httpd.server_close()
            mem_store.close()


class TestItemsHttp(ServerCase):
    def test_create_and_list_item_over_http(self):
        status, created = self.request(
            "POST", "/api/items", {"name": "Coffee mug", "price_cents": 1200, "stock": 30}
        )
        self.assertEqual(status, 201)
        self.assertGreaterEqual(created["id"], 1)
        status, items = self.request("GET", "/api/items")
        self.assertEqual(status, 200)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "Coffee mug")
        self.assertEqual(items[0]["price_cents"], 1200)

    def test_invalid_item_payloads_return_400(self):
        status, body = self.request(
            "POST", "/api/items", {"name": "", "price_cents": 100, "stock": 1}
        )
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        status, _ = self.request(
            "POST", "/api/items", {"name": "X", "price_cents": -5, "stock": 1}
        )
        self.assertEqual(status, 400)
        status, body = self.request("POST", "/api/items", {"name": "X"})
        self.assertEqual(status, 400)

    def test_duplicate_item_name_returns_409(self):
        payload = {"name": "Mug", "price_cents": 100, "stock": 1}
        self.assertEqual(self.request("POST", "/api/items", payload)[0], 201)
        status, body = self.request("POST", "/api/items", payload)
        self.assertEqual(status, 409)
        self.assertIn("error", body)


class TestOrdersHttp(ServerCase):
    def setUp(self):
        super().setUp()
        _, item = self.request(
            "POST", "/api/items", {"name": "Ledger book", "price_cents": 2000, "stock": 5}
        )
        self.item_id = item["id"]

    def test_order_flow_and_stock_change_over_http(self):
        status, order = self.request(
            "POST",
            "/api/orders",
            {"customer_name": "Nina Shop", "item_id": self.item_id, "quantity": 2},
        )
        self.assertEqual(status, 201)
        self.assertEqual(order["total_cents"], 4000)
        status, orders = self.request("GET", "/api/orders")
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["customer_name"], "Nina Shop")
        _, items = self.request("GET", "/api/items")
        self.assertEqual(items[0]["stock"], 3)

    def test_oversell_returns_400(self):
        status, body = self.request(
            "POST",
            "/api/orders",
            {"customer_name": "Too Big", "item_id": self.item_id, "quantity": 99},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    def test_missing_order_fields_return_400(self):
        status, _ = self.request(
            "POST", "/api/orders", {"customer_name": "X", "item_id": self.item_id}
        )
        self.assertEqual(status, 400)


class TestRoutes(ServerCase):
    def test_root_index_lists_endpoints(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("endpoints", body)

    def test_summary_reports_business_numbers(self):
        _, item = self.request(
            "POST", "/api/items", {"name": "Stamp pad", "price_cents": 700, "stock": 2}
        )
        self.request(
            "POST", "/api/orders", {"customer_name": "Zed", "item_id": item["id"], "quantity": 1}
        )
        status, body = self.request("GET", "/api/summary")
        self.assertEqual(status, 200)
        self.assertEqual(body["items"], 1)
        self.assertEqual(body["orders"], 1)
        self.assertEqual(body["revenue_cents"], 700)
        self.assertEqual(len(body["low_stock"]), 1)

    def test_unknown_route_returns_json_404(self):
        status, body = self.request("GET", "/api/nope")
        self.assertEqual(status, 404)
        self.assertIn("error", body)
