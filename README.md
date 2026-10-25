# transitstream-lab

Kafka-based bus telemetry streaming lab on Kubernetes, deployed with Argo CD.

## Layout

| Path | Purpose |
| --- | --- |
| `apps/producer`, `apps/consumer` | Python Kafka producer/consumer and their Dockerfiles |
| `infrastructure/` | kind cluster config, Kafka StatefulSet, base nginx manifests |
| `monitoring/` | Prometheus Helm values |
| `gitops/argocd/` | Argo CD `Application` definitions |
| `gitops/apps/` | Manifests synced by Argo CD (transitstream, kafka-topics) |
| `gitops/apps/kafka-topics/` | Self-service topics, one folder per team ([how to request a topic](gitops/apps/kafka-topics/README.md)) |
| `gitops/platform/policies/` | Kyverno policies that every topic must pass |
| `scripts/` | Repository checks used by CI |

## CI/CD (GitHub Actions)

`.github/workflows/ci.yml` runs on every push and pull request:

1. **python-syntax** – compiles `apps/producer` and `apps/consumer`.
2. **python-imports** – installs and imports the runtime dependencies.
3. **build** (main only) – builds both images and pushes them to
   `ghcr.io/befe2005/transitstream-lab/{producer,consumer}:<short-sha>`.
4. **update-gitops** (main only) – bumps the image tags in
   `gitops/apps/transitstream/deployments.yaml` and commits back to `main`;
   Argo CD then syncs the new images.

## Pulling images from GHCR

If the GHCR packages are private, create the pull secret referenced by the deployments:

```sh
kubectl -n transitstream create secret docker-registry ghcr-registry \
  --docker-server=ghcr.io \
  --docker-username=<github-user> \
  --docker-password=<PAT with read:packages>
```
