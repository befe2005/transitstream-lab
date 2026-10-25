#!/usr/bin/env python3
"""Classify the risk of a Kafka topic change and enforce platform approval.

Compares the topics on the base branch with the topics in the pull request.
Low-risk changes pass. High-risk changes need an approval from a platform
engineer (owners of /gitops/platform/ in CODEOWNERS) on the latest commit.
Impossible changes always fail.

Usage: python3 scripts/topic_risk.py <base_topics_dir> <head_topics_dir>

Environment (optional, enables the approval check):
  GITHUB_TOKEN, GITHUB_REPOSITORY, PR_NUMBER, PR_HEAD_SHA, PR_AUTHOR
  CODEOWNERS (default .github/CODEOWNERS), GITHUB_STEP_SUMMARY
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import yaml

LOW, HIGH, BLOCKED = "low", "high", "blocked"


def load_topics(root: Path) -> dict[str, dict]:
    topics = {}
    for path in sorted((root / "teams").glob("*/*.y*ml")):
        if path.name == "kustomization.yaml":
            continue
        for doc in yaml.safe_load_all(path.read_text()):
            if doc and doc.get("kind") == "KafkaTopic":
                topics[doc["metadata"]["name"]] = doc
    return topics


def as_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def classify(base: dict[str, dict], head: dict[str, dict]) -> list[tuple[str, str, str]]:
    """Return (risk, topic, reason) for every changed topic."""
    changes = []

    for name in sorted(base.keys() - head.keys()):
        changes.append((HIGH, name, "topic is deleted (data is lost and consumers break)"))

    for name in sorted(head.keys() - base.keys()):
        changes.append((LOW, name, "new topic"))

    for name in sorted(base.keys() & head.keys()):
        old, new = base[name], head[name]
        if old == new:
            continue

        old_spec, new_spec = old.get("spec") or {}, new.get("spec") or {}
        old_cfg, new_cfg = old_spec.get("config") or {}, new_spec.get("config") or {}
        old_labels = old["metadata"].get("labels") or {}
        new_labels = new["metadata"].get("labels") or {}
        reasons = []

        old_p, new_p = as_int(old_spec.get("partitions")), as_int(new_spec.get("partitions"))
        if old_p and new_p and new_p < old_p:
            changes.append((BLOCKED, name, f"partitions decreased {old_p} -> {new_p} (Kafka cannot do this)"))
        elif old_p and new_p and new_p > old_p:
            reasons.append(f"partitions increased {old_p} -> {new_p} (key-to-partition mapping changes; "
                           "per-key ordering breaks during the change)")

        if old_spec.get("replicas") != new_spec.get("replicas"):
            reasons.append(f"replicas changed {old_spec.get('replicas')} -> {new_spec.get('replicas')}")

        old_r, new_r = as_int(old_cfg.get("retention.ms")), as_int(new_cfg.get("retention.ms"))
        if old_r and new_r and new_r < old_r:
            reasons.append(f"retention decreased {old_r} -> {new_r} ms (older data is deleted immediately)")

        if old_cfg.get("cleanup.policy") != new_cfg.get("cleanup.policy"):
            reasons.append(f"cleanup.policy changed {old_cfg.get('cleanup.policy')} -> {new_cfg.get('cleanup.policy')}")

        for label in ("data-classification", "team"):
            if old_labels.get(label) != new_labels.get(label):
                reasons.append(f"{label} changed {old_labels.get(label)} -> {new_labels.get(label)}")

        if old_labels.get("tier") == "critical":
            reasons.append("topic is tier=critical")

        if reasons:
            changes.extend((HIGH, name, reason) for reason in reasons)
        elif not any(c[1] == name for c in changes):
            changes.append((LOW, name, "low-risk change (e.g. retention increase, owner, labels)"))

    return changes


def platform_engineers(codeowners: Path) -> set[str]:
    """Owners of /gitops/platform/ in CODEOWNERS are the platform engineers."""
    for line in codeowners.read_text().splitlines():
        parts = line.split()
        if parts and parts[0].rstrip("/") == "/gitops/platform":
            return {p.lstrip("@").lower() for p in parts[1:]}
    return set()


def approvers_on_head() -> set[str]:
    """Users whose latest review is an approval of the current head commit."""
    url = (f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}"
           f"/pulls/{os.environ['PR_NUMBER']}/reviews?per_page=100")
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(request) as response:
        reviews = json.load(response)

    latest: dict[str, dict] = {}
    for review in reviews:
        if review["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[review["user"]["login"].lower()] = review
    return {user for user, review in latest.items()
            if review["state"] == "APPROVED" and review["commit_id"] == os.environ["PR_HEAD_SHA"]}


def main() -> int:
    base_dir, head_dir = Path(sys.argv[1]), Path(sys.argv[2])
    changes = classify(load_topics(base_dir), load_topics(head_dir))
    risks = {risk for risk, _, _ in changes}
    level = BLOCKED if BLOCKED in risks else HIGH if HIGH in risks else LOW

    lines = ["## Topic change risk", ""]
    if not changes:
        lines.append("No topic changes.")
    else:
        lines += ["| Risk | Topic | Change |", "| --- | --- | --- |"]
        lines += [f"| {risk} | `{name}` | {reason} |" for risk, name, reason in changes]
    lines.append("")

    ok = True
    if level == BLOCKED:
        lines.append("❌ **Blocked:** this change is not possible. Revert it.")
        ok = False
    elif level == HIGH:
        engineers = platform_engineers(Path(os.environ.get("CODEOWNERS", ".github/CODEOWNERS")))
        author = os.environ.get("PR_AUTHOR", "").lower()
        if "GITHUB_TOKEN" in os.environ and "PR_NUMBER" in os.environ:
            approved_by = (approvers_on_head() & engineers) - {author}
        else:
            approved_by = set()
        if approved_by:
            lines.append(f"✅ **High risk, approved** by platform engineer(s): {', '.join(sorted(approved_by))}")
        else:
            lines.append("⚠️ **High risk:** needs an approval of the latest commit from a platform engineer "
                         f"({', '.join(sorted(engineers)) or 'none configured'}), not the PR author.")
            ok = False
    else:
        lines.append("✅ **Low risk:** no platform approval needed.")

    report = "\n".join(lines)
    print(report)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as f:
            f.write(report + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
