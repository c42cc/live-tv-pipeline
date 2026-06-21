"""Merge declared XMLTV guides into one epg.xml.gz. Optional: the grid works
without a guide. A source that fails is recorded in the report, never silently
dropped. The guide rots the same way streams do, which is exactly why it lives
in the same pipeline as the playlist."""

from __future__ import annotations

import gzip
import io
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import requests

_TIMEOUT = 60
_HEADERS = {"User-Agent": "live-tv-pipeline/1.0 (+https://github.com/c42cc)"}


@dataclass(slots=True)
class EpgResult:
    url: str
    ok: bool
    channels: int = 0
    programmes: int = 0
    error: str = ""


def _fetch(url: str) -> bytes:
    r = requests.get(url, timeout=_TIMEOUT, headers=_HEADERS)
    r.raise_for_status()
    data = r.content
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def merge_epg(sources: list[str]) -> tuple[bytes, list[EpgResult]]:
    root = ET.Element("tv", {"generator-info-name": "live-tv-pipeline"})
    seen_channels: set[str] = set()
    results: list[EpgResult] = []

    for url in sources:
        try:
            data = _fetch(url)
            src_root = ET.fromstring(data)
        except (requests.RequestException, ET.ParseError, OSError) as e:
            results.append(EpgResult(url=url, ok=False, error=f"{type(e).__name__}: {e}"))
            continue

        ch = pr = 0
        for chan in src_root.findall("channel"):
            cid = chan.get("id", "")
            if cid and cid in seen_channels:
                continue
            if cid:
                seen_channels.add(cid)
            root.append(chan)
            ch += 1
        for prog in src_root.findall("programme"):
            root.append(prog)
            pr += 1
        results.append(EpgResult(url=url, ok=True, channels=ch, programmes=pr))

    buf = io.BytesIO()
    tree = ET.ElementTree(root)
    raw = io.BytesIO()
    tree.write(raw, encoding="utf-8", xml_declaration=True)
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(raw.getvalue())
    return buf.getvalue(), results
