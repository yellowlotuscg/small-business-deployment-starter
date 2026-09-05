# small-business-deployment-starter

A tiny, runnable small-business inventory and ordering API plus the operational
tooling around it: container image, CI, backup and restore, local release
snapshots with rollback, and a health check. Built to show how a small business
app is packaged, tested, operated, and handed off, before any cloud provider is
involved.

Case study repo from [Yellow Lotus Consulting Group](https://yellowlotuscg.com).
The code, tests, and runbooks here are a public engineering sample. This is a
local demonstration project, not a production system and not client data.

## Why this exists

Small business applications need inspectable operations: no automated
tests, no backups, no rollback story, and no way to hand the system to someone
else. This repo is the smallest honest version of that story:

- a real API with a real database and validation;
- tests that prove the behavior;
- backup and restore that is safe to run while the app is live;
- a release flow that refuses to cut a release on failing tests;
- a container that runs the same code, with the same health check, that cloud
  platforms expect;
- written documentation of what is implemented, what is not, and why.

Everything runs locally with no paid services. The Python code is standard
library only: no pip installs, no requirements file, no lockfile.

## Repository map

| Path | Purpose |
| --- | --- |
| `app/store.py` | SQLite storage: items, orders, integer-cents money, WAL, backup API |
| `app/server.py` | JSON HTTP API on the standard library HTTP server |
| `app/seed.py` | Seeds sample items and orders (`python3 -m app.seed`) |
| `app/maintenance.py` | Backup and restore commands |
| `scripts/backup.sh` | WAL-safe backup wrapper |
| `scripts/restore.sh` | Restore wrapper that refuses to clobber without `--force` |
| `scripts/release.sh` | Runs tests, then snapshots a release under `releases/` |
| `scripts/rollback.sh` | Points `releases/current` back to the previous snapshot |
| `scripts/healthcheck.py` | Container health check against `GET /health` |
| `tests/` | Standard library unittest suite (30 tests) |
| `Dockerfile` | Container image for the same app |
| `.github/workflows/tests.yml` | CI: runs the suite on push and pull request |
| `docs/` | Decisions, scope, handoff, training, and cloud reference docs |

## Quick start (local, no container)

Requires Python 3.9+ only.

```bash
python3 -m unittest discover -s tests -q   # 30 tests, all green

python3 -m app.seed                        # creates ./data/app.db with samples
python3 -m app.server                      # listens on http://127.0.0.1:8080
```

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

API surface: `GET /` (index), `GET /health`, `GET|POST /api/items`,
`GET|POST /api/orders`, `GET /api/summary`. All responses are JSON. Money is
always integer cents. Orders fail with 400 when stock is insufficient, and the
write is atomic: no partial stock change.

## Operate it

```bash
DATA_DIR=./data bash scripts/backup.sh             # WAL-safe backup while live
bash scripts/restore.sh data/backups/app-<stamp>.db # refuses overwrite; add --force to replace
bash scripts/release.sh 1.0.0                       # tests must pass first
bash scripts/rollback.sh                            # swap releases/current to previous
PORT=8080 python3 scripts/healthcheck.py            # exit 0 only when healthy
```

`release.sh` snapshots `app/` and `VERSION` under `releases/<version>/` and
points `releases/current` at it. Snapshots are never deleted, and rollback only
swaps pointers. See `docs/decision-case-study.md` for why.

## Container and storage modes

```bash
docker build -t deployment-starter .
# Local persistent example: explicit file-backed mode and named volume.
docker run --rm -p 127.0.0.1:8080:8080 -e MODE=durable -v sbd-data:/data deployment-starter
# Disposable demonstration: explicit in-memory state.
docker run --rm -p 127.0.0.1:8081:8080 -e MODE=stateless deployment-starter
```

The image defaults to `MODE=stateless`. Each process has its own in-memory
database. Restarts lose data, and multiple replicas do not share orders or
inventory. This is suitable only for disposable synthetic demonstrations.

Local Python execution defaults to `MODE=auto`, which tests directory
writability. It cannot detect a persistent volume. A reported `durable` mode
means file-backed SQLite, not a guarantee that the host preserves that file.
Use explicit modes and verify the storage lifecycle yourself.

`MODE=durable` needs persistent local storage and a single app process.
Do not use network filesystem mounts with this WAL-mode SQLite example.
A real multi-replica service requires a shared transactional database and
application changes, not just a cloud deployment switch.

## Implemented vs planned

The repo is intentionally small. `docs/implementation-vs-planned.md` lists
exactly what is implemented and what is deliberately out of scope (auth,
payments, TLS termination, multi-process SQLite, real deployments, observability
beyond `/health`).

## Decision case study

`docs/decision-case-study.md` records the main engineering decisions and their
trade-offs: standard library only, SQLite with WAL and the online backup API,
integer cents, threaded server with one shared store, auto durable/stateless
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

- `docs/support-handoff.md`: how to run, back up, restore, and debug this app,
  written for whoever takes it over.
- `docs/ai-training-guide.md`: two audiences in one file. Parts 1-3 are
  invariants and workflows for AI assistants and new developers working in
  this repo (tests, ASCII docs, version alignment, privacy rules). Part 4 is a
  practical staff training exercise for small-business employees: verifying
  operational claims at the source and reviewing messages for sensitive
  information, using only the synthetic demo facts from the seed data.

## Privacy and data boundary

- All sample data is synthetic (stationery shop items and orders). No real
  customer data, credentials, or private paths are in this repository.
- The app stores only what you POST: item names, prices, stock, customer names,
  order quantities. Logs print request lines only.
- Backups stay where you point them; restore refuses to overwrite non-empty
  targets without `--force`.
- No analytics, no telemetry, no outbound calls in app code, scripts, or CI.

## Limitations

- Single-process server; SQLite file mode is safe across threads in one
  process, not across many app replicas writing the same file.
- No authentication, authorization, TLS, rate limiting, or payment handling:
  the API is a demo of operations, not a hardened public endpoint.
- `releases/` snapshots are local directory copies, not an artifact registry.
- This repo is not a live deployment and no cloud path in it has been executed.

## License

No license is granted. This repository is published for public inspection and
evaluation only; all rights remain with the owner. See the repository owner
(Yellow Lotus Consulting Group) for any other use.
