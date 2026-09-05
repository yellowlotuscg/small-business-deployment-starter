"""Seed the demo database with synthetic sample data. Idempotent by default.

Usage:
  python3 -m app.seed [--data-dir DIR] [--force]

Creates ./data/app.db (or the dir you give) with sample items and orders when
the database is empty. Exits without changes when data already exists.
"""

import argparse
import os

from . import store

SAMPLE_ITEMS = [
    ("Pilot G2 pen pack", 850, 40),
    ("A5 ruled notebook", 425, 60),
    ("Enamel mug, small batch", 1200, 25),
    ("Waxed canvas tote", 3200, 12),
    ("Brass bookmark", 950, 8),
]

SAMPLE_ORDERS = [
    ("Nina Shop", "Pilot G2 pen pack", 4),
    ("Nina Shop", "A5 ruled notebook", 10),
    ("Zed Books", "Enamel mug, small batch", 2),
    ("Zed Books", "Pilot G2 pen pack", 1),
    ("Corner Cafe", "Waxed canvas tote", 3),
    ("Corner Cafe", "Brass bookmark", 5),
]


def main():
    parser = argparse.ArgumentParser(description="Seed sample business data")
    parser.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "./data"))
    parser.add_argument("--force", action="store_true", help="seed even if not empty")
    args = parser.parse_args()

    os.makedirs(args.data_dir, exist_ok=True)
    st = store.Store(os.path.join(args.data_dir, "app.db"))
    try:
        if st.count_items() > 0 and not args.force:
            print("data already present (%d items); use --force to reseed" % st.count_items())
            return 0
        if st.count_items() > 0 and args.force:
            print("reseed requested with --force")
        names = {i["name"] for i in st.list_items()}
        for name, price, stock in SAMPLE_ITEMS:
            if name not in names:
                st.add_item(name, price, stock)
        item_ids = {i["name"]: i["id"] for i in st.list_items()}
        for customer, name, qty in SAMPLE_ORDERS:
            if name in item_ids:
                try:
                    st.add_order(customer, item_ids[name], qty)
                except ValueError as exc:
                    print("skipped order for %s: %s" % (customer, exc))
        summary = st.summary()
        print("seeded %d items, %d orders" % (summary["items"], summary["orders"]))
        print("revenue so far: %d cents (%s)" % (summary["revenue_cents"],
              "$%d.%02d" % divmod(summary["revenue_cents"], 100)))
        return 0
    finally:
        st.close()


if __name__ == "__main__":
    raise SystemExit(main())
