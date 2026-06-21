"""Emit the published artifacts: playlist.m3u, epg.xml.gz, report.json.

report.json is the observability surface: every source's status, every web
resolution, the alive/grace/pruned counts. Monitoring reads it; a human reads it;
nothing about a build's health is hidden."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from .config import DIST_DIR
from .emit_types import BuildReport
from .models import Channel, serialize_m3u
from .validate import ProbeOutcome


def _sort_key(c: Channel) -> tuple[str, str]:
    return (c.group.lower(), c.name.lower())


def write_playlist(outcomes: list[ProbeOutcome]) -> int:
    emitted = sorted((o.channel for o in outcomes if o.emitted), key=_sort_key)
    (DIST_DIR / "playlist.m3u").write_text(serialize_m3u(emitted))
    return len(emitted)


def write_epg(data: bytes) -> None:
    (DIST_DIR / "epg.xml.gz").write_bytes(data)


def write_report(report: BuildReport) -> None:
    report.generated_utc = datetime.now(timezone.utc).isoformat()
    (DIST_DIR / "report.json").write_text(json.dumps(asdict(report), indent=2))
