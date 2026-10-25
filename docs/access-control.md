# Access control

How the self-service Kafka topic platform decides who can change what, and
what a team developer (for example `ticketing-dev`) can and cannot do.

> **Lab note:** CODEOWNERS uses usernames because GitHub teams only exist in
> organizations. In an organization, replace `@befe2005` with teams such as
> `@transitstream/ticketing` and `@transitstream/platform`.

## Layers

```
Developer ──▶ GitHub (PR) ──▶ CI checks ──▶ merge to main ──▶ Argo CD ──▶ Kubernetes ──▶ Kafka
             CODEOWNERS      validate       rulesets          AppProject   Strimzi
             rulesets        topic-risk                        RBAC
```

| # | Layer | Decides | Where |
| --- | --- | --- | --- |
| 1 | Folder ownership (CODEOWNERS) | Who must approve changes to each path | `.github/CODEOWNERS` |
| 2 | Rulesets on `main` | No direct pushes; required checks and code-owner review | GitHub repository rules |
| 3 | Validation (Kyverno + repo checks) | Is the topic valid: name, team domain, sizing, retention, folder | `gitops/platform/policies/kafka-topics/`, `scripts/validate_topics.py` |
| 4 | Risk check | Is the change dangerous; if so, a platform engineer must approve | `scripts/topic_risk.py` |
| 5 | Argo CD AppProject | Team apps may only deploy KafkaTopics into `transitstream` | `gitops/argocd/projects/kafka-topics.yaml` |
| 6 | Argo CD RBAC | What each person sees and can do in Argo CD | `gitops/argocd/config/argocd-rbac-cm.yaml` |

## What a team developer can see (Argo CD)

- Only their own team's Application, e.g. `kafka-topics-ticketing`. Other
  teams' apps, `transitstream`, projects, repositories and clusters are hidden.
- No Sync, Delete or Edit, not even on their own app: Git is the only way to
  change anything.
- `policy.default` is empty, so anything not explicitly allowed is denied.

## What a team developer can change (GitHub + CI)

| If a ticketing developer tries to... | Stopped by |
| --- | --- |
| Push straight to `main` | Ruleset: changes must go through a pull request |
| Create a `bus.*` topic | Naming policy: ticketing may only use `ticketing.*` |
| Set `team: fleet-tracking` on a topic in their own folder | Repo check: the label must match the folder |
| Edit fleet-tracking's topics | CODEOWNERS: fleet-tracking must approve |
| Edit policies (limits, team domains) | CODEOWNERS: `/gitops/platform/` needs platform approval |
| Edit Argo CD config (AppProject, RBAC, ApplicationSet) | CODEOWNERS: `/gitops/argocd/` needs platform approval |
| Edit a CI workflow so checks always pass | CODEOWNERS: `/.github/` needs platform approval |
| Make the risk script say "low risk", or add themselves as a platform engineer | The script and CODEOWNERS are read from `main`, not from the PR |
| Lower retention, delete a topic, add partitions | Risk check: needs a platform engineer's approval of the latest commit |
| Sneak a Deployment into their topic folder | Repo check in CI, and the AppProject refuses it in the cluster |
| Delete a topic by removing its file | `Delete=false` on every topic and `prune: false`: Argo CD never deletes topics |
| Delete a team folder to remove its app | ApplicationSet `applicationsSync: create-update` and `preserveResourcesOnDeletion` |

Workflows run from the PR branch, so a developer *can* make checks look green
in their own PR by editing a workflow. That PR still cannot merge, because
changes to `/.github/` require platform approval. No single layer is perfect;
each covers the others' blind spots.

Team developers have no Kubernetes access: they are Argo CD users only. In
production, only Argo CD's service account should be able to write KafkaTopics.

## Known gaps

| Gap | Impact | Planned fix |
| --- | --- | --- |
| Kafka has no authentication or authorization (`PLAINTEXT`, no authorizer, `auto.create.topics.enable=true`) | Any pod can create, delete or read any topic, bypassing every layer above, including `personal` data | Strimzi-managed Kafka with mTLS, `KafkaUser` ACLs via the same PR flow, auto-create off, topic admin rights only for the topic operator |
| The cluster does not validate topics | Someone with `kubectl` access could create an invalid topic | Kyverno in the cluster, using the same policies |
| Argo CD users are local, not linked to GitHub | `ticketing-dev` is not tied to a real identity | SSO (Dex with GitHub teams); map teams in the `g, ...` RBAC lines |
| One person plays every GitHub role | High-risk changes cannot get an independent approval | Second platform engineer account; a GitHub organization with real teams |
