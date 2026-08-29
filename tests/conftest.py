"""Test environment: the suite must never reach a live model.

app/settings.py loads .env, so without this a developer's real OPENAI_API_KEY would make
the suite billable, slow and non-deterministic. These are set before app.settings is first
imported — its Settings dataclass reads the environment once, when its class body executes.
"""

from __future__ import annotations

import os

os.environ["DEMO_MODE"] = "1"
