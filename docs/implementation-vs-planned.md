# Implemented scope and limits

Implemented: standard-library JSON API, inventory and orders, integer cents,
SQLite transactions, health endpoint, local seed data, backup/restore helpers,
source release snapshots, rollback pointer, Dockerfile and unittest CI.

The tests exercise local behavior. Container verification is recorded separately
from cloud validation. AWS ECS, GCP Cloud Run and Azure Container Apps paths are
reference configurations only; no live cloud deployment is claimed.

Not implemented: authentication, payments, TLS termination, managed database
adapters, production monitoring, distributed storage or a production release
controller. A source rollback pointer does not restart the service or reverse
data changes. The app is for synthetic data only.

Container mode defaults to stateless. Each process owns independent in-memory
data that disappears on restart. Local auto mode checks only writability and
cannot prove persistence. Durable means file-backed, with survival determined
by the actual storage lifecycle. Do not use network filesystem WAL SQLite.
