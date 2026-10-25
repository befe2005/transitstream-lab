#!/usr/bin/env python3
"""Repository-level checks for self-service Kafka topics.

Kyverno policies validate each KafkaTopic on its own. This script covers what
they cannot see: where a file lives and how files relate to each other.

Usage: python3 scripts/validate_topics.py [topics_root]
"""
import sys
from pathlib import Path

import yaml

TOPICS_ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "gitops/apps/kafka-topics")
TEAMS_DIR = TOPICS_ROOT / "teams"
NAMESPACE = "transitstream"

errors: list[str] = []


def error(path: Path, message: str) -> None:
    errors.append(f"{path}: {message}")


def load_kustomization(directory: Path) -> list[str]:
    path = directory / "kustomization.yaml"
    if not path.exists():
        error(directory, "missing kustomization.yaml")
        return []
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("resources") or []


# Every team folder must be listed in the root kustomization.
root_resources = set(load_kustomization(TOPICS_ROOT))
team_dirs = sorted(p for p in TEAMS_DIR.iterdir() if p.is_dir())
for team_dir in team_dirs:
    if f"teams/{team_dir.name}" not in root_resources:
        error(TOPICS_ROOT / "kustomization.yaml", f"teams/{team_dir.name} is not listed in resources")

seen_topics: dict[str, Path] = {}

for team_dir in team_dirs:
    team = team_dir.name
    listed = set(load_kustomization(team_dir))

    for path in sorted(team_dir.glob("*.y*ml")):
        if path.name == "kustomization.yaml":
            continue

        # A file that is not listed is silently never deployed.
        if path.name not in listed:
            error(path, f"not listed in {team_dir / 'kustomization.yaml'}")

        try:
            docs = [d for d in yaml.safe_load_all(path.read_text()) if d]
        except yaml.YAMLError as exc:
            error(path, f"invalid YAML: {exc}")
            continue

        if len(docs) != 1:
            error(path, f"must contain exactly one resource, found {len(docs)}")
            continue

        doc = docs[0]
        metadata = doc.get("metadata") or {}
        labels = metadata.get("labels") or {}
        topic = (doc.get("spec") or {}).get("topicName")

        # Team folders may only contain topics, nothing else can be deployed this way.
        if doc.get("kind") != "KafkaTopic" or not str(doc.get("apiVersion", "")).startswith("kafka.strimzi.io/"):
            error(path, f"only kafka.strimzi.io KafkaTopic resources are allowed, found {doc.get('kind')}")
            continue

        # The folder decides the team: CODEOWNERS protects folders, not labels.
        if labels.get("team") != team:
            error(path, f"label team must be '{team}' (the folder name), found '{labels.get('team')}'")

        if metadata.get("namespace") != NAMESPACE:
            error(path, f"metadata.namespace must be '{NAMESPACE}'")

        # topicName is the source of truth; the resource and file names derive from it.
        if topic:
            expected = str(topic).replace(".", "-")
            if metadata.get("name") != expected or path.stem != expected:
                error(path, f"metadata.name and file name must both be '{expected}' (topicName '{topic}' "
                            f"with dots as dashes), found name '{metadata.get('name')}' in '{path.name}'")

        if topic in seen_topics:
            error(path, f"topic '{topic}' is already defined in {seen_topics[topic]}")
        elif topic:
            seen_topics[topic] = path

    for resource in sorted(listed):
        if not (team_dir / resource).exists():
            error(team_dir / "kustomization.yaml", f"lists '{resource}' which does not exist")

if errors:
    print(f"Found {len(errors)} problem(s):")
    for message in errors:
        print(f"  - {message}")
    sys.exit(1)

print(f"OK: {len(seen_topics)} topics across {len(team_dirs)} teams")
