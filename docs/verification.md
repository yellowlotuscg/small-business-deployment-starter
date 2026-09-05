# Verification receipt

Local Python unittest execution: 30 tests passed, including actual loopback HTTP
requests, storage validation and backup/restore checks.

Container build and stateless smoke test verified locally after an earlier
Docker Hub timeout. Commands: `docker build -t yl-deployment-starter:proof .`,
`docker run -d --name yl-proof-acceptance --publish 127.0.0.1:18091:8080 yl-deployment-starter:proof`,
and `docker exec yl-proof-acceptance python3 scripts/healthcheck.py`.
The build completed; the healthcheck returned `healthy: stateless` with exit 0.
HTTP GET `/health`, `/api/items` and `/api/summary` returned 200. Health reported
memory storage and stateless mode; the fresh instance had no items or orders.
The test container was stopped afterward. This verifies the local image and
basic read endpoints, not cloud deployment, mounted persistence or load handling.

AWS ECS, GCP Cloud Run and Azure Container Apps paths: documented references,
not live deployments. No cloud resources were created. This is intentional
scope for the public MVP, not a request for account access.

Local execution and cloud/template validation are separate facts. CI records
its own result for the published commit. See README for privacy and production
limitations.
