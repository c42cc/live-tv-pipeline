"""Fetch + merge the declared upstreams into one candidate channel list.

No retries/backoff: a fetch is one attempt. A failure is recorded as a typed
SourceResult (observable in report.json), not swallowed and not papered over —
the last-seen grace in validate.py is what absorbs a transient upstream blip,
deliberately and visibly, never silently.
"""

from __future__ import annotations

from dataclasses import dataclass

import requests

from .config import Config
from .models import Channel, parse_m3u

_TIMEOUT = 30
_HEADERS = {"User-Agent": "live-tv-pipeline/1.0 (+https://github.com/c42cc)"}


@dataclass(slots=True)
class SourceResult:
    ref: str
    ok: bool
    count: int
    error: str = ""


def _get_m3u(url: str, ref: str) -> tuple[list[Channel], SourceResult]:
    try:
        r = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS)
        r.raise_for_status()
    except requests.RequestException as e:
        return [], SourceResult(ref=ref, ok=False, count=0, error=f"{type(e).__name__}: {e}")
    chans = parse_m3u(r.text, source_ref=ref)
    # Tag every channel with a consistent group derived from its source if it has none.
    return chans, SourceResult(ref=ref, ok=True, count=len(chans))


def fetch_all(cfg: Config) -> tuple[list[Channel], list[SourceResult]]:
    channels: list[Channel] = []
    results: list[SourceResult] = []

    for code in cfg.countries:
        ref = f"country:{code}"
        chans, res = _get_m3u(cfg.country_url.format(code=code), ref)
        for c in chans:
            if not c.group:
                c.group = code.upper()
        channels.extend(chans)
        results.append(res)

    for cat in cfg.categories:
        ref = f"category:{cat}"
        chans, res = _get_m3u(cfg.category_url.format(category=cat), ref)
        for c in chans:
            if not c.group:
                c.group = cat.capitalize()
        channels.extend(chans)
        results.append(res)

    for i, url in enumerate(cfg.m3u_upstreams):
        ref = f"m3u:{url.rsplit('/', 1)[-1] or i}"
        chans, res = _get_m3u(url, ref)
        channels.extend(chans)  # full playlists already carry group-title; keep as-is
        results.append(res)

    for spec in cfg.channels_explicit:
        channels.append(
            Channel(
                name=spec["name"],
                url=spec["url"],
                tvg_id=spec.get("tvg_id", ""),
                tvg_logo=spec.get("tvg_logo", ""),
                group=spec.get("group", "Custom"),
                source_ref=f"explicit:{spec['name']}",
            )
        )
        results.append(SourceResult(ref=f"explicit:{spec['name']}", ok=True, count=1))

    return channels, results


def dedupe(channels: list[Channel]) -> list[Channel]:
    """Keep the first occurrence of each identity (tvg-id, else URL)."""
    seen: set[str] = set()
    out: list[Channel] = []
    for c in channels:
        k = c.key()
        if k in seen:
            continue
        seen.add(k)
        out.append(c)
    return out


FEATURED_GROUP = "\u2605 Featured"


def apply_featured(channels: list[Channel], patterns: list[str]) -> int:
    """Re-tag marquee channels (by name substring) into a Featured group that the
    emitter surfaces first. Reuses already-validated channels from the full catalog
    instead of maintaining a separate hand-curated list of fragile URLs."""
    if not patterns:
        return 0
    n = 0
    for c in channels:
        low = c.name.lower()
        if any(p in low for p in patterns):
            c.group = FEATURED_GROUP
            n += 1
    return n


def apply_exclude(channels: list[Channel], cfg: Config) -> list[Channel]:
    out: list[Channel] = []
    for c in channels:
        if c.tvg_id and c.tvg_id.lower() in cfg.exclude_tvg_ids:
            continue
        low = c.name.lower()
        if any(token in low for token in cfg.exclude_name_contains):
            continue
        out.append(c)
    return out
