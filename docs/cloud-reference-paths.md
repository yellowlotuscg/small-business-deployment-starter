# Cloud reference paths (reference only, unexecuted, not blocked)

This document maps the container image built by this repository to three
serverless container platforms: AWS ECS on Fargate, Google Cloud Run, and
Azure Container Apps. It is written so a reader who already has a cloud
account can follow a path, but **nothing in this document has been executed**.
This project had no cloud account access while this document was written and
has no live deployment anywhere. Every section below carries the status label
**reference only, unexecuted, not blocked**.

Official vendor documentation links were checked and reachable on 2026-09-05.
Commands and configuration shapes follow those pages; replace every placeholder
(`ACCOUNT-ID`, `REGION`, `PROJECT-ID`, `RESOURCE-GROUP`, registry paths, and so
on) with your own values before use.

## Container contract and safety

The image listens on port 8080 with `HOST=0.0.0.0`, serves `/health`, and
now defaults explicitly to `MODE=stateless`. Writability does not prove
persistence. Each instance has its own in-memory inventory and orders.
Use one instance for a disposable demonstration. Even one instance loses
state on replacement. This is not a production transactional deployment.

The application has no authentication, TLS termination or abuse controls.
Keep cloud ingress private or authenticated at the platform boundary. Do not
place customer records in this example. These templates require registry,
identity, network and logging prerequisites configured by the operator.
They are reference configurations, not a one-command production installer.

Build the image locally with `docker build -t deployment-starter:1.0.0 .`.
Registry publishing and cloud resource creation are outside local verification.
Cloud use can incur charges for compute, logs, registries and networking;
review pricing and teardown requirements before executing any reference command.

## SQLite and network filesystems: not recommended

Do not point durable SQLite at a network filesystem mount on any of these
platforms (Amazon EFS, Cloud Run storage mounts, Azure Files). SQLite relies on
POSIX file locking semantics that network filesystems do not reliably provide,
and WAL recovery assumes local, ordered writes. Symptoms range from
`database is locked` errors to silent corruption after an instance is recycled
mid-write. If you need shared, multi-replica storage, use a managed database
service instead of SQLite; that is a deliberate non-goal of this demo repo.

## AWS: ECS on Fargate

Official pages (checked 2026-09-05):

- Getting started with Fargate:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-fargate.html
- Task definitions:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/taskdefinitions.html
- Fargate task storage (ephemeral storage behavior):
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-storage.html
- Data volumes (EFS mounts):
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/using_data_volumes.html
- Container health checks:
  https://docs.aws.amazon.com/AmazonECS/latest/developerguide/container-health.html

### Reference task definition (taskdef.json)

Stateless default, no volume. The health check runs the same script the
Dockerfile HEALTHCHECK uses.

```json
{
  "family": "deployment-starter",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::ACCOUNT-ID:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "ACCOUNT-ID.dkr.ecr.REGION.amazonaws.com/deployment-starter:1.0.0",
      "portMappings": [{ "containerPort": 8080, "protocol": "tcp" }],
      "environment": [{ "name": "MODE", "value": "stateless" }],
      "healthCheck": {
        "command": ["CMD-SHELL", "python3 scripts/healthcheck.py"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 10
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/deployment-starter",
          "awslogs-region": "REGION",
          "awslogs-stream-prefix": "app"
        }
      }
    }
  ]
}
```

### Reference commands

```bash
aws ecr create-repository --repository-name deployment-starter
aws ecr get-login-password --region REGION | \
  docker login --username AWS --password-stdin ACCOUNT-ID.dkr.ecr.REGION.amazonaws.com
docker tag deployment-starter:1.0.0 \
  ACCOUNT-ID.dkr.ecr.REGION.amazonaws.com/deployment-starter:1.0.0
docker push ACCOUNT-ID.dkr.ecr.REGION.amazonaws.com/deployment-starter:1.0.0

aws ecs register-task-definition --cli-input-json file://taskdef.json

# Service in a VPC with a public subnet; or use an Application Load Balancer
# with a target group whose health check path is /health on port 8080.
aws ecs create-service \
  --cluster YOUR-CLUSTER \
  --service-name deployment-starter \
  --task-definition deployment-starter \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration \
  "awsvpcConfiguration={subnets=SUBNET-IDS,securityGroups=SG-ID,assignPublicIp=ENABLED}"
```

Platform notes:

- Fargate instances get ephemeral storage that is not preserved across task
  stops or replacements; explicit MODE=stateless makes this a disposable demonstration only.
- Persistent production storage requires a different database design, not an EFS mount for this WAL SQLite application.
- A load balancer target group health check on `GET /health` (HTTP 200) is the
  usual routing health signal; the container-level health check above is
  separate and optional.

## Google Cloud: Cloud Run

Official pages (checked 2026-09-05):

- What is Cloud Run:
  https://cloud.google.com/run/docs/overview/what-is-cloud-run
- Container runtime contract (port, filesystem, lifecycle):
  https://cloud.google.com/run/docs/container-contract
- Deploying:
  https://cloud.google.com/run/docs/deploying
- Health checks (startup, liveness, readiness probes):
  https://cloud.google.com/run/docs/configuring/healthchecks
- Configure containers (port and resources):
  https://cloud.google.com/run/docs/configuring/services/containers

### Reference commands

```bash
gcloud run deploy deployment-starter \
  --image REGION-docker.pkg.dev/PROJECT-ID/REPOSITORY/deployment-starter:1.0.0 \
  --region REGION \
  --port 8080 \
  --cpu 1 \
  --memory 512Mi \
  --min-instances 0 \
  --max-instances 1 \
  --set-env-vars MODE=stateless \
  --no-allow-unauthenticated \
  --platform managed
```

Cloud Run injects `PORT` itself and expects the container to listen on
`0.0.0.0`; this image's fixed `8080` matches the default, and `--port 8080`
states it explicitly. With `MODE=stateless` the app never tries to write
durable data, which matches the platform lifecycle.

### Reference service YAML (service.yaml, equivalent shape)

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: deployment-starter
  namespace: PROJECT-ID
  labels:
    cloud.googleapis.com/location: REGION
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "0"
        autoscaling.knative.dev/maxScale: "1"
    spec:
      containerConcurrency: 20
      containers:
        - image: REGION-docker.pkg.dev/PROJECT-ID/REPOSITORY/deployment-starter:1.0.0
          env:
            - name: MODE
              value: stateless
          ports:
            - name: http1
              containerPort: 8080
          resources:
            limits:
              cpu: "1"
              memory: 512Mi
```

Deploy with `gcloud run services replace service.yaml`. Health check probes
(startup, liveness, and readiness in preview) are configured in the console or
in YAML per the health checks page; a startup HTTP probe on `GET /health` is
the natural fit for this image.

Platform notes:

- Cloud Run's container filesystem is an in-memory filesystem: writes consume
  instance memory and do not survive instance stops. This image's stateless
  default is the correct mode here.
- Cloud Run storage mounts (Cloud Storage FUSE, Filestore NFS, and the
  ephemeral-disk preview) are network or instance-scoped storage; none of them
  is a safe home for durable SQLite, per the section above. Durable data on
  Cloud Run means a managed database such as Cloud SQL, which is out of scope
  for this demo.

## Microsoft Azure: Container Apps

Official pages (checked 2026-09-05):

- Container Apps overview:
  https://learn.microsoft.com/en-us/azure/container-apps/overview
- Quickstart (portal):
  https://learn.microsoft.com/en-us/azure/container-apps/quickstart-portal
- Containers configuration:
  https://learn.microsoft.com/en-us/azure/container-apps/containers
- Environment variables:
  https://learn.microsoft.com/en-us/azure/container-apps/environment-variables
- Health probes:
  https://learn.microsoft.com/en-us/azure/container-apps/health-probes
- Storage mounts:
  https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts
- Scaling (including scale to zero):
  https://learn.microsoft.com/en-us/azure/container-apps/scale-app

### Reference commands

```bash
# One-time: a Container Apps environment
az containerapp env create \
  --name YOUR-ENVIRONMENT \
  --resource-group RESOURCE-GROUP \
  --location REGION

# Stateless default deploy (scale to zero allowed with min-replicas 0)
az containerapp create \
  --name deployment-starter \
  --resource-group RESOURCE-GROUP \
  --environment YOUR-ENVIRONMENT \
  --image YOUR-REGISTRY/deployment-starter:1.0.0 \
  --ingress internal \
  --target-port 8080 \
  --cpu 0.25 \
  --memory 0.5Gi \
  --min-replicas 0 \
  --max-replicas 1 \
  --env-vars MODE=stateless
```

Container Apps sends requests to `--target-port` (8080 here), so the ingress
and this image's listener agree. Per the health probes page, an HTTP probe with
path `/health` on port 8080 can be attached so the platform restarts an
instance that stops answering.

Platform notes:

- Container Apps sandboxes have ephemeral local storage; writes are lost when
  the replica is recycled. Scale to zero (`--min-replicas 0`) means even a
  durable mount is idle when no requests arrive, which is another reason the
  stateless default is the right demo posture.
- Do not use Azure Files for this WAL SQLite example. Production persistence needs a database adapter and managed transactional store.

## Status recap

| Platform | Status | Executed here? | Default mode recommended |
| --- | --- | --- | --- |
| AWS ECS Fargate | reference only | no | stateless, no volume |
| Google Cloud Run | reference only | no | stateless, no volume |
| Azure Container Apps | reference only | no | stateless, no volume |

No cloud account, no cloud credentials, and no deployed service exist for this
project. If you execute any of these paths, record what you changed and where,
and update `docs/implementation-vs-planned.md` so the repo's claims stay honest.
