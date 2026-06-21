"""Orchestrate one build: manifest -> candidates -> validate -> publish artifacts.

Exit codes:
  0  build healthy
  2  build ran but the grid is too empty to ship (loud, CI-failing)
  3  mechanism failure (preflight / manifest / unwritable) — PipelineError
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter

from . import PipelineError
from .config import DIST_DIR, load_config
from .emit import write_epg, write_playlist, write_report
from .emit_types import BuildReport
from .epg import merge_epg
from .fetch import apply_exclude, dedupe, fetch_all
from .preflight import preflight
from .resolve_web import resolve_web_sources
from .validate import validate_and_select


def build(limit: int | None = None) -> BuildReport:
    t0 = time.monotonic()
    preflight()
    cfg = load_config()

    fetched, source_results = fetch_all(cfg)
    web_channels, web_results = resolve_web_sources(cfg.website_sources)
    candidates = fetched + web_channels

    candidates = apply_exclude(dedupe(candidates), cfg)
    deduped_n = len(candidates)
    if limit:
        candidates = candidates[:limit]

    outcomes, _state = validate_and_select(candidates, cfg.validate)

    labels = Counter(o.state for o in outcomes)
    alive_n = labels.get("alive", 0)
    grace_n = labels.get("grace", 0)
    emitted_n = write_playlist(outcomes)

    report = BuildReport(
        candidates=len(fetched) + len(web_channels),
        deduped=deduped_n,
        alive=alive_n,
        grace=grace_n,
        emitted=emitted_n,
        pruned=labels.get("pruned", 0),
        dead_unknown=labels.get("dead-unknown", 0),
        pass_rate=round(alive_n / len(candidates), 4) if candidates else 0.0,
        sources=[{"ref": r.ref, "ok": r.ok, "count": r.count, "error": r.error} for r in source_results],
        web=[{"name": r.name, "ok": r.ok, "stream_url": r.stream_url, "error": r.error,
              "expires_in_s": r.expires_in_s} for r in web_results],
        duration_s=round(time.monotonic() - t0, 1),
    )

    if cfg.epg_enabled and cfg.epg_sources:
        epg_bytes, epg_results = merge_epg(cfg.epg_sources)
        write_epg(epg_bytes)
        report.epg = {
            "enabled": True,
            "bytes": len(epg_bytes),
            "sources": [{"url": r.url, "ok": r.ok, "channels": r.channels,
                         "programmes": r.programmes, "error": r.error} for r in epg_results],
        }
    else:
        report.epg = {"enabled": False}
        stale = DIST_DIR / "epg.xml.gz"
        if stale.exists():
            stale.unlink()  # never leave a misleading empty/stale guide behind

    write_report(report)
    return report


def _print_summary(report: BuildReport) -> None:
    print("\n=== live-tv-pipeline build ===")
    print(f"  candidates (deduped): {report.deduped}")
    print(f"  alive: {report.alive}   grace: {report.grace}   emitted: {report.emitted}")
    print(f"  pruned: {report.pruned}   never-alive: {report.dead_unknown}")
    print(f"  pass-rate: {report.pass_rate:.1%}   duration: {report.duration_s}s")
    bad = [s for s in report.sources if not s["ok"]]
    if bad:
        print(f"  !! {len(bad)} upstream(s) failed (channels held by last-seen grace):")
        for s in bad:
            print(f"     - {s['ref']}: {s['error']}")
    for w in report.web:
        flag = "ok " if w["ok"] else "!! "
        exp = w.get("expires_in_s")
        note = ""
        if exp is not None:
            hrs = exp / 3600
            note = f"  [VOLATILE: token expires in {hrs:.1f}h]" if exp < 12 * 3600 else f"  [expires in {hrs:.1f}h]"
        target = (w["stream_url"][:80] + "...") if w["ok"] and len(w["stream_url"]) > 80 else (w["stream_url"] or w["error"])
        print(f"  web {flag}{w['name']}: {target}{note}")
    if report.epg.get("enabled"):
        for s in report.epg.get("sources", []):
            flag = "ok " if s["ok"] else "!! "
            print(f"  epg {flag}{s['url']}: {s.get('channels',0)} ch / {s.get('programmes',0)} prog {s.get('error','')}")
    print(f"  artifacts -> {DIST_DIR}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the validated live-TV playlist.")
    ap.add_argument("--limit", type=int, default=None, help="cap candidates (smoke test)")
    ap.add_argument("--min-emitted", type=int, default=20, help="fail the build if fewer channels survive")
    args = ap.parse_args(argv)

    try:
        report = build(limit=args.limit)
    except PipelineError as e:
        print(f"\nMECHANISM FAILURE (halt, don't heal):\n{e}", file=sys.stderr)
        return 3

    _print_summary(report)
    if report.emitted < args.min_emitted:
        print(f"\nGRID TOO EMPTY: {report.emitted} < min {args.min_emitted}. Refusing to publish a broken grid.",
              file=sys.stderr)
        return 2
    print("\nBUILD HEALTHY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
