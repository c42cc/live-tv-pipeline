"""Shared report shape (its own module to avoid import cycles)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BuildReport:
    generated_utc: str = ""
    candidates: int = 0
    deduped: int = 0
    alive: int = 0
    grace: int = 0
    emitted: int = 0
    pruned: int = 0
    dead_unknown: int = 0
    pass_rate: float = 0.0
    sources: list[dict] = field(default_factory=list)
    web: list[dict] = field(default_factory=list)
    epg: dict = field(default_factory=dict)
    duration_s: float = 0.0
