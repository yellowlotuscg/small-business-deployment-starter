"""Tests for the SQLite store layer: items, orders, money as integer cents."""
import os
import sqlite3
import tempfile
import unittest

from app import store


class StoreBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "test.db")
        self.s = store.Store(self.db_path)

    def tearDown(self):
        self.s.close()
        self._tmp.cleanup()


class TestItems(StoreBase):
    def test_add_and_list_item(self):
        item_id = self.s.add_item("A5 notebook", 425, 60)
        items = self.s.list_items()
        self.assertEqual(len(items), 1)
        row = items[0]
        self.assertEqual(row["id"], item_id)
        self.assertEqual(row["name"], "A5 notebook")
        self.assertEqual(row["price_cents"], 425)
        self.assertEqual(row["stock"], 60)
        self.assertIn("created_at", row)

    def test_rejects_blank_name_negative_price_and_negative_stock(self):
        with self.assertRaises(ValueError):
            self.s.add_item("   ", 100, 1)
        with self.assertRaises(ValueError):
            self.s.add_item("Pen", -1, 1)
        with self.assertRaises(ValueError):
            self.s.add_item("Pen", 100, -2)

    def test_duplicate_item_name_rejected(self):
        self.s.add_item("Pen", 100, 5)
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.add_item("Pen", 200, 5)


class TestOrders(StoreBase):
    def setUp(self):
        super().setUp()
        self.pen_id = self.s.add_item("Pen", 150, 10)

    def test_order_records_total_and_decrements_stock(self):
        order_id = self.s.add_order("Ada Lovelace", self.pen_id, 2)
        orders = self.s.list_orders()
        self.assertEqual(len(orders), 1)
        o = orders[0]
        self.assertEqual(o["id"], order_id)
        self.assertEqual(o["customer_name"], "Ada Lovelace")
        self.assertEqual(o["quantity"], 2)
        self.assertEqual(o["total_cents"], 300)
        self.assertEqual(o["item_name"], "Pen")
        item = self.s.list_items()[0]
        self.assertEqual(item["stock"], 8)

    def test_order_with_too_many_units_rejected_and_no_partial_write(self):
        with self.assertRaises(ValueError):
            self.s.add_order("Bob", self.pen_id, 99)
        self.assertEqual(self.s.count_orders(), 0)
        self.assertEqual(self.s.list_items()[0]["stock"], 10)

    def test_order_for_missing_item_rejected(self):
        with self.assertRaises(ValueError):
            self.s.add_order("Carol", 99999, 1)

    def test_order_requires_customer_name(self):
        with self.assertRaises(ValueError):
            self.s.add_order("", self.pen_id, 1)


class TestModeAndHealth(StoreBase):
    def test_file_store_uses_wal_mode(self):
        mode = self.s._db.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode, "wal")

    def test_health_reports_durable_file_storage(self):
        h = self.s.health()
        self.assertEqual(h["status"], "ok")
        self.assertEqual(h["mode"], "durable")
        self.assertEqual(h["storage"], "file")
        self.assertTrue(h["writable"])

    def test_memory_store_health_reports_stateless(self):
        mem = store.Store(None)
        try:
            h = mem.health()
            self.assertEqual(h["mode"], "stateless")
            self.assertEqual(h["storage"], "memory")
        finally:
            mem.close()
