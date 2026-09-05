"""SQLite storage for the demo small business app.

All money is stored as integer cents. One shared connection plus a lock keeps
file mode (WAL) and memory mode consistent inside one process.
"""

import os
import shutil
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    stock INTEGER NOT NULL CHECK (stock >= 0),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT NOT NULL,
    item_id INTEGER NOT NULL REFERENCES items(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    total_cents INTEGER NOT NULL CHECK (total_cents >= 0),
    created_at TEXT NOT NULL
);
"""

LOW_STOCK_WARNING = 5


def utcnow():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clean_text(value, label, max_len=80):
    if not isinstance(value, str):
        raise ValueError("%s must be text" % label)
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("%s cannot be empty" % label)
    if len(cleaned) > max_len:
        raise ValueError("%s must be %d characters or fewer" % (label, max_len))
    return cleaned


def _clean_int(value, label, minimum=None):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s must be a whole number" % label)
    if minimum is not None and value < minimum:
        raise ValueError("%s cannot be below %d" % (label, minimum))
    return value


class Store:
    """A small SQLite-backed store. Pass path=None for in-memory mode."""

    def __init__(self, path):
        self.path = path
        self.memory = path is None
        self._lock = threading.RLock()
        if not self.memory:
            parent = os.path.dirname(os.path.abspath(path))
            os.makedirs(parent, exist_ok=True)
        connect_path = path if path is not None else ":memory:"
        self._db = sqlite3.connect(connect_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.execute("PRAGMA busy_timeout = 5000")
        if not self.memory:
            self._db.execute("PRAGMA journal_mode = WAL")
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self):
        with self._lock:
            try:
                self._db.close()
            except sqlite3.Error:
                pass

    # ------------------------------------------------------------------ items

    def add_item(self, name, price_cents, stock):
        name = _clean_text(name, "name")
        price_cents = _clean_int(price_cents, "price_cents", minimum=0)
        stock = _clean_int(stock, "stock", minimum=0)
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO items (name, price_cents, stock, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name, price_cents, stock, utcnow()),
            )
            self._db.commit()
            return cur.lastrowid

    def list_items(self):
        with self._lock:
            rows = self._db.execute(
                "SELECT id, name, price_cents, stock, created_at "
                "FROM items ORDER BY id"
            ).fetchall()
        return [dict(r) for r in rows]

    def count_items(self):
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    # ----------------------------------------------------------------- orders

    def add_order(self, customer_name, item_id, quantity):
        customer_name = _clean_text(customer_name, "customer_name", max_len=120)
        item_id = _clean_int(item_id, "item_id", minimum=1)
        quantity = _clean_int(quantity, "quantity", minimum=1)
        with self._lock:
            row = self._db.execute(
                "SELECT id, name, price_cents, stock FROM items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if row is None:
                raise ValueError("item not found")
            if quantity > row["stock"]:
                raise ValueError(
                    "insufficient stock: %d available, %d requested"
                    % (row["stock"], quantity)
                )
            total = row["price_cents"] * quantity
            cur = self._db.execute(
                "INSERT INTO orders "
                "(customer_name, item_id, quantity, total_cents, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (customer_name, item_id, quantity, total, utcnow()),
            )
            self._db.execute("UPDATE items SET stock = stock - ? WHERE id = ?",
                             (quantity, item_id))
            self._db.commit()
            return cur.lastrowid

    def list_orders(self):
        with self._lock:
            rows = self._db.execute(
                "SELECT o.id, o.customer_name, o.item_id, i.name AS item_name, "
                "o.quantity, o.total_cents, o.created_at "
                "FROM orders o JOIN items i ON i.id = o.item_id ORDER BY o.id"
            ).fetchall()
        return [dict(r) for r in rows]

    def count_orders(self):
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]

    def revenue_cents(self):
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(SUM(total_cents), 0) FROM orders"
            ).fetchone()
        return row[0]

    def summary(self):
        low_stock = []
        with self._lock:
            rows = self._db.execute(
                "SELECT name, stock FROM items WHERE stock < ? ORDER BY stock, name",
                (LOW_STOCK_WARNING,),
            ).fetchall()
            low_stock = [dict(r) for r in rows]
        return {
            "items": self.count_items(),
            "orders": self.count_orders(),
            "revenue_cents": self.revenue_cents(),
            "low_stock": low_stock,
        }

    # ------------------------------------------------------------ backup

    def backup_to(self, dest_path):
        """Online WAL-safe backup using the sqlite3 backup API."""
        dest_path = os.path.abspath(dest_path)
        parent = os.path.dirname(dest_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self._lock:
            dest = sqlite3.connect(dest_path)
            try:
                self._db.backup(dest)
            finally:
                dest.close()
        return dest_path

    def health(self):
        try:
            with self._lock:
                self._db.execute("SELECT 1").fetchone()
            alive = True
        except sqlite3.Error:
            alive = False
        writable = True
        if self.memory:
            storage = "memory"
            mode = "stateless"
        else:
            storage = "file"
            mode = "durable"
            writable = os.access(self.path, os.W_OK) if os.path.exists(self.path) else False
        return {
            "status": "ok" if alive and writable else "degraded",
            "storage": storage,
            "mode": mode,
            "writable": writable,
        }


def restore_from(backup_path, target_path, force=False):
    """Copy a backup file into target_path after an integrity check.

    Refuses to overwrite a non-empty target unless force=True. Never touches
    anything outside the given paths.
    """
    backup_path = os.path.abspath(backup_path)
    target_path = os.path.abspath(target_path)
    if not os.path.isfile(backup_path):
        raise ValueError("backup file not found: %s" % backup_path)
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0 and not force:
        raise ValueError(
            "target already exists and is not empty; pass force=True to overwrite: %s"
            % target_path
        )
    parent = os.path.dirname(target_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp_path = target_path + ".restore-tmp"
    shutil.copyfile(backup_path, tmp_path)
    try:
        conn = sqlite3.connect(tmp_path)
        try:
            result = conn.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.Error as exc:
        os.remove(tmp_path)
        raise ValueError("backup is not a readable SQLite file: %s" % exc)
    if result != "ok":
        os.remove(tmp_path)
        raise ValueError("backup failed integrity check: %s" % result)
    os.replace(tmp_path, target_path)
    return target_path
