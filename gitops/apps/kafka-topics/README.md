# Kafka topics (self-service)

Topics are requested by pull request. CI validates the request, your team
reviews it, and Argo CD creates the topic after merge. Do not `kubectl apply`
topics by hand.

## Request a topic

1. Create `teams/<your-team>/<domain>-<dataset>-<event>.yaml`:

   ```yaml
   apiVersion: kafka.strimzi.io/v1beta2
   kind: KafkaTopic
   metadata:
     name: bus-gps-position            # topicName with dots replaced by dashes
     namespace: transitstream
     labels:
       strimzi.io/cluster: transitstream
       team: fleet-tracking            # must match the folder name
       owner: <github-username>        # person accountable for the topic
       data-classification: internal   # public | internal | personal
       tier: standard                  # standard | critical
   spec:
     topicName: bus.gps.position       # <domain>.<dataset>.<event>
     partitions: 3
     replicas: 1
     config:
       retention.ms: 86400000          # 1 day
   ```

2. Add the file name to `teams/<your-team>/kustomization.yaml`.
3. Open a pull request. The **Topic validation** check tells you exactly what to fix.

## Rules

| Rule | Limit |
| --- | --- |
| Name | `<domain>.<dataset>.<event>`, lowercase, your team's domain only |
| Partitions | 1–12 (cannot be reduced later) |
| Replicas | 1–3; 3 replicas require `min.insync.replicas: 2` |
| Retention | required, 1 hour – 7 days; max 3 days for `personal` data |
| Configs allowed | `retention.ms`, `cleanup.policy`, `min.insync.replicas`, `max.message.bytes` (≤ 1 MiB), `compression.type` |

Need something outside these limits, or a new team/domain? Ask the platform team.
Onboarding a team means adding its folder and adding it to the `teamDomains` map in
`gitops/platform/policies/kafka-topics/02-naming.yaml`; Argo CD creates the team's
Application (`kafka-topics-<team>`) automatically.

## Approvals

Every pull request needs the **Topic validation** and **Topic risk** checks to pass
and an approval from your team (CODEOWNERS). The risk check compares your change
with `main`:

| Change | Risk | Approval |
| --- | --- | --- |
| New topic, retention increase, owner/label change | low | your team |
| Delete or rename a topic, lower retention, more partitions, change replicas, `cleanup.policy`, `data-classification` or team, any change to a `tier: critical` topic | high | your team **and** a platform engineer, on the latest commit |
| Fewer partitions | blocked | not possible in Kafka |

More partitions is high risk because Kafka assigns messages to partitions by key
(for example bus ID): adding partitions changes that mapping, so events for one
bus can briefly arrive out of order.

## Run the checks locally

```sh
python3 scripts/validate_topics.py
kyverno apply gitops/platform/policies/kafka-topics/*.yaml --resource gitops/apps/kafka-topics/teams/<team>/<topic>.yaml
```

Policies live in `gitops/platform/policies/kafka-topics/` and are owned by the platform team.
