# Deployment decision case study

## Scenario

A fictional small shop needs an inventory and order demonstration that another
operator can understand. No client engagement, savings or production outcome
is claimed. The engineering goal is a reproducible application plus recovery
and handoff evidence.

## Decisions and tradeoffs

1. Python standard library keeps local setup small. The HTTP server is a demo
   server, not a hardened production gateway.
2. SQLite and integer cents make atomic inventory changes and monetary values
   easy to inspect. A shared connection is guarded for threads within one process.
3. Local file-backed operation supports backup demonstrations. Online SQLite
   backups capture consistent database state, but restoration must be coordinated
   with a stopped writer. A database restore is not an application rollback.
4. Container mode is explicitly stateless. Auto mode only checks directory
   writability and cannot discover persistence. In-memory data is not shared.
5. Release snapshots preserve source and move a current pointer. They do not
   restart a running service, deploy an image, or migrate database schemas.
6. Start with a single host for a small demo. Managed containers can reduce host
   maintenance, but require registry, identity, networking and cost decisions.
7. Kubernetes is justified by orchestration requirements and operating capacity,
   not by portfolio appearance. This small example does not require it.

## Verification

The unittest suite exercises storage validation, HTTP requests, backup/restore
and release guards. See CI for the tested commit. Cloud templates are unexecuted
references. No infrastructure availability, recovery-time objective or customer
outcome has been measured.

## Production gap

Before real use: authentication, authorization, TLS, abuse controls, request
limits, monitoring, retention policy, durable shared storage if needed, restore
drills, deployment automation, cost review and an identified support owner.
