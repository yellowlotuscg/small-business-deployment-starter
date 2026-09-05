"""Backup and restore commands for the demo app. Safe, path-scoped, no clobber.

Usage:
  python3 -m app.maintenance backup --data-dir ./data [--out PATH]
  python3 -m app.maintenance restore --backup PATH [--data-dir ./data] [--force]
"""

import argparse
import os
import time

from . import store


def _timestamp():
    return time.strftime("%Y%m%d-%H%M%S", time.localtime())


def cmd_backup(args):
    db_path = os.path.join(os.path.abspath(args.data_dir), "app.db")
    if not os.path.isfile(db_path):
        raise SystemExit("no database at %s; run seed first" % db_path)
    st = store.Store(db_path)
    try:
        if args.out:
            out = os.path.abspath(args.out)
        else:
            out = os.path.join(os.path.abspath(args.data_dir), "backups",
                               "app-%s.db" % _timestamp())
        st.backup_to(out)
    finally:
        st.close()
    check = store.Store(out)
    try:
        items = check.count_items()
        orders = check.count_orders()
    finally:
        check.close()
    size = os.path.getsize(out)
    print("backup written: %s" % out)
    print("size bytes: %d" % size)
    print("integrity: ok")
    print("rows in backup: %d items, %d orders" % (items, orders))


def cmd_restore(args):
    data_dir = os.path.abspath(args.data_dir)
    target = os.path.join(data_dir, "app.db")
    if not os.path.isfile(args.backup):
        raise SystemExit("backup file not found: %s" % args.backup)
    if os.path.exists(target) and not args.force:
        raise SystemExit(
            "target %s already exists; pass --force to replace it" % target
        )
    for sidecar in (target + "-wal", target + "-shm"):
        if os.path.exists(sidecar):
            os.remove(sidecar)
    store.restore_from(args.backup, target, force=args.force)
    st = store.Store(target)
    try:
        items = st.count_items()
        orders = st.count_orders()
    finally:
        st.close()
    print("restored to: %s" % target)
    print("integrity: ok")
    print("rows after restore: %d items, %d orders" % (items, orders))


def main():
    parser = argparse.ArgumentParser(description="Backup and restore helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup", help="write a WAL-safe SQLite backup")
    p_backup.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "./data"))
    p_backup.add_argument("--out", default=None, help="explicit backup path")

    p_restore = sub.add_parser("restore", help="restore a backup into a data dir")
    p_restore.add_argument("--backup", required=True, help="path to the .db backup")
    p_restore.add_argument("--data-dir", default=os.environ.get("DATA_DIR", "./data"))
    p_restore.add_argument("--force", action="store_true",
                           help="replace an existing database")

    args = parser.parse_args()
    if args.command == "backup":
        cmd_backup(args)
    elif args.command == "restore":
        cmd_restore(args)
    else:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
