"""Seed scenarios for Causality.

Each scenario is a self-contained `ScenarioBundle` with realistic-looking traces,
spans, and logs plus a hidden ground-truth `RootCause`. Distractor spans/logs are
included on purpose so retrieval/ranking has something to do.
"""

from typing import Dict, List

from ..models import ScenarioBundle
from . import scenarios

# Registered in demo order — slow-db-query is the default "wow in 10s" scenario.
_BUILDERS = [
    scenarios.slow_db_query,
    scenarios.cascading_timeout,
    scenarios.bad_deploy,
    scenarios.noisy_neighbor,
]


def build_all() -> Dict[str, ScenarioBundle]:
    """Build every scenario fresh. Deterministic — safe to call repeatedly."""
    bundles: Dict[str, ScenarioBundle] = {}
    for builder in _BUILDERS:
        bundle = builder()
        bundles[bundle.scenario_key] = bundle
    return bundles


def scenario_keys() -> List[str]:
    return [b.__name__.replace("_", "-") for b in _BUILDERS]
