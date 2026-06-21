"""Load + validate sources.yaml. A malformed manifest HALTS (it is our mechanism,
not content churn)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import PipelineError

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_PATH = REPO_ROOT / "sources.yaml"
DIST_DIR = REPO_ROOT / "dist"
STATE_PATH = REPO_ROOT / "state" / "last_seen.json"


@dataclass(slots=True)
class ValidatePolicy:
    ffprobe_timeout_s: int = 8
    max_workers: int = 60
    time_budget_s: int = 900
    prune_after_failures: int = 3
    grace_days: int = 2


@dataclass(slots=True)
class Config:
    countries: list[str]
    categories: list[str]
    m3u_upstreams: list[str]
    channels_explicit: list[dict]
    website_sources: list[dict]
    exclude_tvg_ids: set[str]
    exclude_name_contains: list[str]
    featured_name_contains: list[str]
    country_url: str
    category_url: str
    epg_enabled: bool
    epg_sources: list[str]
    validate: ValidatePolicy = field(default_factory=ValidatePolicy)


def _require(d: dict, *path: str):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            raise PipelineError(f"sources.yaml missing required key: {'.'.join(path)}")
        cur = cur[p]
    return cur


def load_config(path: Path | None = None) -> Config:
    p = path or SOURCES_PATH
    if not p.exists():
        raise PipelineError(f"sources.yaml not found at {p}")
    try:
        raw = yaml.safe_load(p.read_text()) or {}
    except yaml.YAMLError as e:
        raise PipelineError(f"sources.yaml is not valid YAML: {e}") from e

    include = raw.get("include") or {}
    upstreams = _require(raw, "upstreams")
    if not isinstance(upstreams, dict) or "country_url" not in upstreams or "category_url" not in upstreams:
        raise PipelineError("sources.yaml: upstreams must define country_url and category_url")
    exclude = raw.get("exclude") or {}
    epg = raw.get("epg") or {}
    vraw = raw.get("validate") or {}

    countries = [str(c).strip().lower() for c in (include.get("countries") or [])]
    categories = [str(c).strip().lower() for c in (include.get("categories") or [])]
    m3u_upstreams = [str(u).strip() for u in (include.get("m3u_upstreams") or [])]
    web = include.get("website_sources") or []
    explicit = include.get("channels_explicit") or []

    if not (countries or categories or m3u_upstreams or web or explicit):
        raise PipelineError(
            "sources.yaml declares no content (countries/categories/website_sources/"
            "channels_explicit all empty). Refusing to emit an empty grid."
        )
    for w in web:
        if not w.get("url") or not w.get("name"):
            raise PipelineError(f"website_sources entry missing name/url: {w!r}")
    for c in explicit:
        if not c.get("url") or not c.get("name"):
            raise PipelineError(f"channels_explicit entry missing name/url: {c!r}")

    return Config(
        countries=countries,
        categories=categories,
        m3u_upstreams=m3u_upstreams,
        channels_explicit=explicit,
        website_sources=web,
        exclude_tvg_ids={str(x).strip().lower() for x in (exclude.get("tvg_ids") or [])},
        exclude_name_contains=[str(x).strip().lower() for x in (exclude.get("name_contains") or [])],
        featured_name_contains=[str(x).strip().lower() for x in (include.get("featured") or [])],
        country_url=upstreams["country_url"],
        category_url=upstreams["category_url"],
        epg_enabled=bool(epg.get("enabled", False)),
        epg_sources=list(epg.get("sources") or []),
        validate=ValidatePolicy(
            ffprobe_timeout_s=int(vraw.get("ffprobe_timeout_s", 8)),
            max_workers=int(vraw.get("max_workers", 60)),
            time_budget_s=int(vraw.get("time_budget_s", 900)),
            prune_after_failures=int(vraw.get("prune_after_failures", 3)),
            grace_days=int(vraw.get("grace_days", 2)),
        ),
    )
