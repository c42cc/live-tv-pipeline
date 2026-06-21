#!/usr/bin/env python3
"""Acceptance check for the PUBLISHED artifacts — not the build internals.

Re-reads dist/playlist.m3u exactly as the appliance would, randomly samples real
channels, and ffprobes them to confirm a genuine A/V stream answers. This is the
content-plane analog of 'watch the pixels': we verify the actual bytes the device
will receive, independently of the build that produced them.

Exit 0 = artifacts are real and a sample genuinely plays. Nonzero = halt.
"""

from __future__ import annotations

import gzip
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.models import parse_m3u  # noqa: E402

PLAYLIST = ROOT / "dist" / "playlist.m3u"
EPG = ROOT / "dist" / "epg.xml.gz"
SAMPLE = 12
PROBE_TIMEOUT = 10


def _probe(url: str) -> bool:
    try:
        p = subprocess.run(
            ["ffprobe", "-v", "error", "-rw_timeout", str(PROBE_TIMEOUT * 1_000_000),
             "-i", url, "-show_entries", "stream=codec_type", "-of", "csv=p=0"],
            capture_output=True, text=True, timeout=PROBE_TIMEOUT + 4,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    out = (p.stdout or "").strip()
    return p.returncode == 0 and ("video" in out or "audio" in out)


def main() -> int:
    if not PLAYLIST.exists():
        print(f"FAIL: {PLAYLIST} does not exist — run a build first.", file=sys.stderr)
        return 1

    text = PLAYLIST.read_text()
    if not text.startswith("#EXTM3U"):
        print("FAIL: playlist.m3u missing #EXTM3U header.", file=sys.stderr)
        return 1
    channels = parse_m3u(text)
    if not channels:
        print("FAIL: playlist parsed to zero channels.", file=sys.stderr)
        return 1

    groups = sorted({c.group for c in channels if c.group})
    print(f"playlist.m3u: {len(channels)} channels across {len(groups)} groups")
    print(f"  groups: {', '.join(groups[:18])}{' ...' if len(groups) > 18 else ''}")

    if EPG.exists():
        try:
            head = gzip.decompress(EPG.read_bytes())[:64].decode("utf-8", "replace")
            print(f"epg.xml.gz: {EPG.stat().st_size} bytes, valid gzip, starts {head[:40]!r}")
        except OSError as e:
            print(f"FAIL: epg.xml.gz is not valid gzip: {e}", file=sys.stderr)
            return 1

    sample = random.sample(channels, min(SAMPLE, len(channels)))
    print(f"\nProbing {len(sample)} random channels (proving they truly play):")
    alive = 0
    for c in sample:
        ok = _probe(c.url)
        alive += ok
        print(f"  [{'PLAY' if ok else 'dead'}] {c.group} / {c.name}")

    rate = alive / len(sample)
    print(f"\nsample play-rate: {alive}/{len(sample)} = {rate:.0%}")
    if rate < 0.5:
        print("FAIL: fewer than half the sampled channels played. Grid is not trustworthy.", file=sys.stderr)
        return 1
    print("OK: published artifacts are real and a representative sample genuinely plays.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
