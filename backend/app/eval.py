"""Eval harness + scorecard (Saturday #5).

Each seed scenario has a known root cause. The harness scores whether the engine's
top hypothesis matches. Until the pipeline lands, running this still does useful
work: it validates seed integrity (every ground-truth evidence id actually exists)
and prints the scorecard skeleton.

Run:  python -m app.eval
"""

from __future__ import annotations

from typing import List, Optional

from .models import Hypothesis, RootCause, ScenarioBundle
from . import seeds


def score_top_hypothesis(top: Optional[Hypothesis], truth: RootCause) -> dict:
    """Match = top hypothesis hits >=2 ground-truth keywords AND cites at least one
    real evidence span. Deliberately fuzzy — we score "did it find the cause", not
    "did it phrase it our way"."""
    if top is None:
        return {"match": False, "keyword_hits": 0, "evidence_overlap": 0, "reason": "no hypothesis"}

    text = f"{top.title} {top.explanation}".lower()
    hits = [k for k in truth.keywords if k in text]
    evidence_overlap = len(set(top.evidence_span_ids) & set(truth.evidence_span_ids))
    match = len(hits) >= 2 and evidence_overlap >= 1
    return {
        "match": match,
        "keyword_hits": len(hits),
        "hit_terms": hits,
        "evidence_overlap": evidence_overlap,
    }


def validate_seed(bundle: ScenarioBundle) -> List[str]:
    """Cheap integrity checks so a broken seed fails loudly, not silently."""
    problems: List[str] = []
    span_ids = {s.id for s in bundle.spans}
    log_ids = {l.id for l in bundle.logs}
    for sid in bundle.root_cause.evidence_span_ids:
        if sid not in span_ids:
            problems.append(f"root_cause references missing span {sid}")
    for lid in bundle.root_cause.evidence_log_ids:
        if lid not in log_ids:
            problems.append(f"root_cause references missing log {lid}")
    # Every span's parent must exist within the bundle.
    for s in bundle.spans:
        if s.parent_id and s.parent_id not in span_ids:
            problems.append(f"span {s.id} has dangling parent {s.parent_id}")
    return problems


def run() -> int:
    bundles = seeds.build_all()
    print(f"\nCausality eval — {len(bundles)} scenarios\n" + "=" * 56)

    integrity_ok = True
    for key, bundle in bundles.items():
        problems = validate_seed(bundle)
        flag = "OK " if not problems else "BAD"
        integrity_ok = integrity_ok and not problems
        print(f"[{flag}] {key:<18} {len(bundle.spans):>2} spans  {len(bundle.logs):>2} logs  -> {bundle.root_cause.culprit_service}")
        for p in problems:
            print(f"        ! {p}")

    print("-" * 56)
    print("Hypothesis scoring: PENDING (engine not wired yet — Saturday #4).")
    print("Once wired, this prints: scenario | top hypothesis | match? | confidence")
    print("=" * 56 + "\n")
    return 0 if integrity_ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
