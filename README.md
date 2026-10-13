# small-business-deployment-starter

A tiny, runnable small-business inventory and ordering API, plus the operational
tooling around it: a container image, CI, backup and restore, local release
snapshots with rollback, and a health check. It shows how a small business
app is packaged, tested, operated, and handed off before any cloud provider
is involved.

Case study repo from [Yellow Lotus Consulting Group](https://yellowlotuscg.com).
The code, tests, and runbooks here are a public engineering sample. This is a
local demonstration project, not a production system, and it contains no
client data.

## Why this exists

A small shop application is hard to hand to someone else when tests, backups,
and rollback are missing. This repo is a small working copy of that handoff:

- a real API with a real database and validation;
- tests that prove the behavior;
- a backup you can take while the app is running, and a restore that leaves
  an existing database in place unless you pass `--force` (stop the server
  before a forced restore);
- a release flow that refuses to cut a release when tests fail;
- a container that runs this same app and checks `GET /health`;
- written notes on what is implemented, what is left out, and why.

Everything here runs locally. The Python code uses the standard library only:
no pip installs, no requirements file, and no lockfile. CI and the container
image use Python 3.12.

## Get the code

```bash
git clone https://github.com/yellowlotuscg/small-business-deployment-starter.git
cd small-business-deployment-starter
```

## Repository map

| Path | Purpose |
| --- | --- |
| `app/store.py` | SQLite storage: items, orders, integer-cents money, WAL, backup API |
| `app/server.py` | JSON HTTP API on the standard library HTTP server |
| `app/seed.py` | Seeds sample items and orders (`python3 -m app.seed`) |
| `app/maintenance.py` | Backup and restore commands |
| `scripts/backup.sh` | WAL-safe backup wrapper |
| `scripts/restore.sh` | Restore wrapper that refuses to replace an existing database without `--force` |
| `scripts/release.sh` | Runs tests, then snapshots a release under `releases/` |
| `scripts/rollback.sh` | Points `releases/current` at the previous snapshot |
| `scripts/healthcheck.py` | Health check that requests `GET /health` |
| `tests/` | Standard library unittest suite (30 tests) |
| `Dockerfile` | Container image for the same app |
| `.github/workflows/tests.yml` | CI: runs the suite on push and pull request to `main` |
| `docs/` | Decisions, scope, handoff, training, verification, and cloud reference docs |
| `LICENSE` | MIT License |

## Quick start (local, no container)

From the repository root, with Python 3.12:

```bash
python3 -m unittest discover -s tests -q   # 30 tests

python3 -m app.seed                        # writes ./data/app.db when that database is empty
python3 -m app.server                      # listens on http://127.0.0.1:8080
```

`app.seed` does nothing when the database already contains items. It prints
a notice and does not insert the sample orders again.

In another terminal:

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/api/summary
curl -s -X POST http://127.0.0.1:8080/api/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"Coffee mug","price_cents":1200,"stock":30}'
curl -s -X POST http://127.0.0.1:8080/api/orders \
  -H 'Content-Type: application/json' \
  -d '{"customer_name":"Corner Cafe","item_id":1,"quantity":2}'
```

After `app.seed`, item 1 is "Pilot G2 pen pack", and it still has stock, so
the order above is for that pen pack. The coffee mug response includes the
new item's `id`. Use that id to order the mug. On a fresh seed the mug is id 6.

The routes are `GET /` (service name, version, and the route list), `GET /health`,
`GET` and `POST /api/items`, `GET` and `POST /api/orders`, and `GET /api/summary`.
Those responses are JSON. Prices and order totals are integer cents.
`GET /api/summary` returns the item count, the order count, `revenue_cents`,
and `low_stock` (items whose stock is below 5).

Creating an item or an order returns 201 and the new row. A duplicate item
name returns 409. An unknown route returns 404. Invalid input returns 400.
An order for more units than the item has in stock returns 400 and writes
nothing: no order row, and no stock change. Other HTTP methods get the
standard library's default 501 HTML response.

## Operate it

Run these from the repository root.

```bash
DATA_DIR=./data bash scripts/backup.sh              # WAL-safe backup while the server is up
bash scripts/restore.sh data/backups/app-<stamp>.db # refuses to replace an existing database
bash scripts/release.sh 1.0.0                       # tests must pass first
bash scripts/rollback.sh                            # point releases/current at the previous snapshot
PORT=8080 python3 scripts/healthcheck.py            # exit 0 only when /health reports status ok
```

`restore.sh` will not replace `DATA_DIR/app.db` (default `./data/app.db`) when
that file already exists. Pass `--force` only after the server is stopped.
The running process keeps the database connection it opened at startup, so
replacing the file underneath it does not load the restored data into that
process.

`release.sh` copies `app/` and `VERSION` to `releases/<version>/` and points
the `releases/current` symlink at that directory. A version string has to
look like `1.2.3`. If that snapshot directory already exists, the script
exits and leaves it alone. Snapshots are never deleted. The state file
remembers one previous version. Rollback swaps current and previous, so a
second run swaps them back. Rollback does not restart the server and does
not change the database. See `docs/decision-case-study.md`.

`healthcheck.py` requests `http://127.0.0.1:$PORT/health` (port 8080 when
`PORT` is unset) and exits 0 only when the JSON `status` is `ok`.

## Container and storage modes

```bash
docker build -t deployment-starter .
# Local persistent example: explicit file-backed mode and named volume.
docker run --rm -p 127.0.0.1:8080:8080 -e MODE=durable -v sbd-data:/data deployment-starter
# Disposable demonstration: explicit in-memory state.
docker run --rm -p 127.0.0.1:8081:8080 -e MODE=stateless deployment-starter
```

The image defaults to `MODE=stateless` and sets `HOST=0.0.0.0` and `PORT=8080`.
Each process has its own in-memory database. Restarts lose data, and multiple
replicas do not share orders or inventory. This is suitable only for
disposable synthetic demonstrations.

Local Python execution defaults to `MODE=auto`, which tests directory
writability, and to `HOST=127.0.0.1`. Auto mode cannot detect a persistent
volume. A reported `durable` mode means file-backed SQLite, not a guarantee
that the host preserves that file. Use explicit modes and verify the storage
lifecycle yourself.

`MODE=durable` needs persistent local storage and a single app process.
Do not use network filesystem mounts with this WAL-mode SQLite example.
A real multi-replica service requires a shared transactional database and
application changes, not just a cloud deployment switch.

## Implemented vs planned

The repo is intentionally small. `docs/implementation-vs-planned.md` lists
what is implemented and what is deliberately out of scope (auth, payments,
TLS termination, multi-process SQLite, real deployments, observability beyond
`/health`).

## Decision case study

`docs/decision-case-study.md` records the main engineering decisions and their
trade-offs: standard library only, SQLite with WAL and the online backup API,
integer cents, a threaded server with one shared store, auto durable/stateless
mode, and local release snapshots instead of a container registry.

## Cloud reference paths (not executed here)

`docs/cloud-reference-paths.md` maps this image to AWS ECS (Fargate), GCP Cloud
Run, and Azure Container Apps with official vendor documentation links: the
container contract each platform expects, the port and health probe wiring, and
explicit mode settings with persistence limitations.

Status label for those sections: **reference only, unexecuted, not blocked**.
This public MVP intentionally has no cloud account access and no live
deployment; nothing in this repo is deployed anywhere. The paths are documented
so a reader with an account can follow them, with the caveats (ephemeral
filesystems, volume requirements) called out per platform.

## Handoff and training

- `docs/support-handoff.md` explains how to run, back up, restore, release,
  roll back, and debug this app.
- `docs/ai-training-guide.md` is a facilitator-led exercise for small-business
  staff. It uses the synthetic app only: check an AI-written stock note
  against the live summary, catch a wrong quantity and an unsupported delivery
  promise, and keep customer records off the AI tool.
- `docs/verification.md` records the local test run and a past local container
  smoke test. Cloud paths in that note were not executed.

## Privacy and data boundary

- Sample data is synthetic: pens, notebooks, an enamel mug, a tote, a
  bookmark, and invented shop names (Nina Shop, Zed Books, Corner Cafe).
  The repository has no real customer data, credentials, or private paths.
- Stored fields are item name, price in cents, stock, customer name, order
  quantity, the computed order total, and timestamps. The server prints a
  startup line and one line per request to stderr. A database or internal
  error also prints a traceback there.
- Backups go under the data directory, or to the path you pass to
  `scripts/backup.sh`. `restore.sh` will not replace an existing database
  without `--force`.
- The application code, shell scripts, and test workflow do not send
  analytics or telemetry.

## Limitations

- Single-process server. SQLite file mode is safe across threads in one
  process, not across many app replicas writing the same file.
- No authentication, authorization, TLS, rate limiting, or payment handling.
  The API demonstrates operations. It is not a hardened public endpoint.
- `releases/` snapshots are local directory copies of `app/` and `VERSION`,
  not an artifact registry. Rollback only swaps the current pointer.
- This repo is not a live deployment, and no cloud path in it has been executed.

## License

MIT License. Copyright (c) 2026 Matthew Coggins. See [LICENSE](LICENSE).
