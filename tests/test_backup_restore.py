"""Backup and restore round trips on temporary sample data, WAL safety."""
import os
import sqlite3
import tempfile
import unittest

from app import store


def seed_sample(s):
    pen = s.add_item("Pilot G2 pen pack", 850, 40)
    book = s.add_item("A5 notebook", 425, 60)
    mug = s.add_item("Enamel mug", 1200, 25)
    s.add_order("Nina Shop", pen, 4)
    s.add_order("Nina Shop", book, 10)
    s.add_order("Zed Books", mug, 2)
    s.add_order("Zed Books", pen, 1)


class BackupRestoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.src_path = os.path.join(self._tmp.name, "src.db")
        self.src = store.Store(self.src_path)
        seed_sample(self.src)

    def tearDown(self):
        self.src.close()
        self._tmp.cleanup()

    def test_backup_restore_roundtrip_preserves_every_row(self):
        backup_path = os.path.join(self._tmp.name, "backups", "sample-2026.db")
        self.src.backup_to(backup_path)
        self.assertTrue(os.path.isfile(backup_path))

        target_path = os.path.join(self._tmp.name, "restored.db")
        store.restore_from(backup_path, target_path)

        restored = store.Store(target_path)
        try:
            conn = restored._db
            integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
            self.assertEqual(integrity, "ok")
            self.assertEqual(restored.count_items(), self.src.count_items())
            self.assertEqual(restored.count_orders(), self.src.count_orders())
            self.assertEqual(restored.list_items(), self.src.list_items())
            self.assertEqual(restored.list_orders(), self.src.list_orders())
            self.assertEqual(
                restored.summary()["revenue_cents"], self.src.summary()["revenue_cents"]
            )
        finally:
            restored.close()

    def test_restore_refuses_to_overwrite_without_force(self):
        backup_path = os.path.join(self._tmp.name, "sample.db")
        self.src.backup_to(backup_path)
        target_path = os.path.join(self._tmp.name, "existing.db")
        existing = store.Store(target_path)
        existing.add_item("Pre-existing item", 100, 1)
        existing.close()
        with self.assertRaises(ValueError):
            store.restore_from(backup_path, target_path)
        conn = sqlite3.connect(target_path)
        try:
            count = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 1, "original data must survive a refused restore")

    def test_force_restore_replaces_target(self):
        backup_path = os.path.join(self._tmp.name, "sample.db")
        self.src.backup_to(backup_path)
        target_path = os.path.join(self._tmp.name, "existing.db")
        existing = store.Store(target_path)
        existing.add_item("Pre-existing item", 100, 1)
        existing.close()
        store.restore_from(backup_path, target_path, force=True)
        restored = store.Store(target_path)
        try:
            self.assertEqual(restored.count_items(), self.src.count_items())
            names = [i["name"] for i in restored.list_items()]
            self.assertNotIn("Pre-existing item", names)
        finally:
            restored.close()

    def test_backup_of_memory_store_is_possible(self):
        mem = store.Store(None)
        mem.add_item("Memory item", 500, 3)
        backup_path = os.path.join(self._tmp.name, "mem.db")
        mem.backup_to(backup_path)
        mem.close()
        check = store.Store(backup_path)
        try:
            self.assertEqual(check.count_items(), 1)
            self.assertEqual(check.health()["mode"], "durable")
        finally:
            check.close()

    def test_restore_rejects_missing_backup_file(self):
        with self.assertRaises(ValueError):
            store.restore_from(
                os.path.join(self._tmp.name, "does-not-exist.db"),
                os.path.join(self._tmp.name, "out.db"),
            )
