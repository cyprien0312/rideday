"""Registered ride-day providers. Add a new site = add an adapter + one line here."""
from __future__ import annotations

from lib.providers.champions import Champions
from lib.providers.phillip_island import PhillipIsland

PROVIDERS: list = [Champions(), PhillipIsland()]
