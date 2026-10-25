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

## Run the checks locally

```sh
python3 scripts/validate_topics.py
kubectl kustomize gitops/apps/kafka-topics > /tmp/rendered.yaml
kyverno apply gitops/platform/policies/kafka-topics/*.yaml --resource /tmp/rendered.yaml
```

Policies live in `gitops/platform/policies/kafka-topics/` and are owned by the platform team.
