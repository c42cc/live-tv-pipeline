"""Live-TV content pipeline.

Turns the declarative sources.yaml into one validated playlist.m3u (+ epg.xml.gz)
that the appliance fetches from a stable URL. Appliance/content separation
(Invariant 0): this code never touches the device.
"""

from __future__ import annotations

__all__ = ["PipelineError"]


class PipelineError(RuntimeError):
    """A mechanism failure in the pipeline itself (broken dep, malformed manifest,
    unwritable output). Raised loudly and typed so a broken instrument can never
    read as a measurement. Distinct from expected *content* churn (a dead stream),
    which is recorded in report.json, not raised."""
