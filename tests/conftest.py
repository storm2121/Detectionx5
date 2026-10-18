"""Shared test configuration.

Hypothesis runs derandomised by default so CI is deterministic (AGENT_RULES §3.4); set
``HYPOTHESIS_PROFILE=explore`` locally to search with fresh random examples.
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

settings.register_profile(
    "deterministic",
    derandomize=True,
    deadline=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile("explore", deadline=None, max_examples=2000)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "deterministic"))
