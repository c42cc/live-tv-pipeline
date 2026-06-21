"""Resolve 'direct website' sources to a concrete stream URL at build time.

A web page is not a stream. yt-dlp turns the page into the current HLS/DASH URL,
which then flows through the exact same validation as every other channel — so a
stale or expired web token is caught by the liveness probe upstream and reported,
never shipped blind to the device.
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass

from .models import Channel

_RESOLVE_TIMEOUT = 45
# googlevideo (YouTube) and many CDNs embed a unix-epoch expiry as /expire/<ts>/
# or ?expire=<ts>. Surfacing it turns "the channel silently 403s in 6 hours" into
# an observable number the report and monitoring can act on.
_EXPIRE = re.compile(r"[/?&]expire[/=](\d{10})")


@dataclass(slots=True)
class WebResult:
    name: str
    page_url: str
    ok: bool
    stream_url: str = ""
    error: str = ""
    expires_in_s: int | None = None  # None = no detectable expiry (treated as stable)


def _expiry_seconds(url: str) -> int | None:
    m = _EXPIRE.search(url)
    if not m:
        return None
    return int(m.group(1)) - int(time.time())


def _resolve_one(name: str, page_url: str) -> WebResult:
    try:
        proc = subprocess.run(
            ["yt-dlp", "-g", "-f", "best", "--no-warnings", "--no-playlist", page_url],
            capture_output=True,
            text=True,
            timeout=_RESOLVE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return WebResult(name=name, page_url=page_url, ok=False, error="yt-dlp timeout")
    except OSError as e:
        return WebResult(name=name, page_url=page_url, ok=False, error=f"yt-dlp spawn failed: {e}")

    if proc.returncode != 0:
        err = (proc.stderr or "").strip().splitlines()
        return WebResult(name=name, page_url=page_url, ok=False, error=err[-1] if err else "yt-dlp failed")

    urls = [u for u in proc.stdout.strip().splitlines() if u.startswith("http")]
    if not urls:
        return WebResult(name=name, page_url=page_url, ok=False, error="no stream URL extracted")
    return WebResult(name=name, page_url=page_url, ok=True, stream_url=urls[0],
                     expires_in_s=_expiry_seconds(urls[0]))


def resolve_web_sources(specs: list[dict]) -> tuple[list[Channel], list[WebResult]]:
    channels: list[Channel] = []
    results: list[WebResult] = []
    for spec in specs:
        name = spec["name"]
        res = _resolve_one(name, spec["url"])
        results.append(res)
        if res.ok:
            channels.append(
                Channel(
                    name=name,
                    url=res.stream_url,
                    tvg_id=spec.get("tvg_id", ""),
                    tvg_logo=spec.get("tvg_logo", ""),
                    group=spec.get("group", "Web"),
                    source_ref=f"web:{name}",
                )
            )
    return channels, results
