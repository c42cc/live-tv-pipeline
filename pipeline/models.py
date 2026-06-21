"""Channel model + M3U (de)serialization. One home for the (channel, url) tuple."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

_EXTINF_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
_EXTINF_LINE = re.compile(r"^#EXTINF:(?P<dur>-?\d+)\s*(?P<attrs>.*?),(?P<name>.*)$")


@dataclass(slots=True)
class Channel:
    """A single live channel: metadata + exactly one stream URL."""

    name: str
    url: str
    tvg_id: str = ""
    tvg_logo: str = ""
    group: str = ""
    source_ref: str = ""  # provenance, e.g. "country:us", "category:news", "web:DW English"
    extra_attrs: dict[str, str] = field(default_factory=dict)

    def key(self) -> str:
        """Dedup identity: prefer tvg-id, else the stream URL."""
        return f"id:{self.tvg_id.lower()}" if self.tvg_id else f"url:{self.url}"

    def to_extinf(self) -> str:
        attrs: dict[str, str] = {}
        if self.tvg_id:
            attrs["tvg-id"] = self.tvg_id
        if self.tvg_logo:
            attrs["tvg-logo"] = self.tvg_logo
        if self.group:
            attrs["group-title"] = self.group
        for k, v in self.extra_attrs.items():
            attrs.setdefault(k, v)
        rendered = " ".join(f'{k}="{v}"' for k, v in attrs.items())
        head = f"#EXTINF:-1 {rendered}" if rendered else "#EXTINF:-1"
        return f"{head},{self.name}\n{self.url}"

    def with_group(self, group: str) -> "Channel":
        return replace(self, group=group)


def parse_m3u(text: str, source_ref: str = "") -> list[Channel]:
    """Parse an M3U/M3U8 playlist into Channels. Tolerant of #EXTGRP and blank
    lines; ignores entries with no URL (a channel with no stream is not a channel)."""
    channels: list[Channel] = []
    name = ""
    tvg_id = tvg_logo = group = ""
    extra: dict[str, str] = {}
    pending = False
    ext_group = ""

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m = _EXTINF_LINE.match(line)
            if not m:
                continue
            attrs = dict(_EXTINF_ATTR.findall(m.group("attrs")))
            tvg_id = attrs.pop("tvg-id", "")
            tvg_logo = attrs.pop("tvg-logo", "")
            group = attrs.pop("group-title", "")
            extra = attrs
            name = m.group("name").strip()
            pending = True
        elif line.startswith("#EXTGRP:"):
            ext_group = line.split(":", 1)[1].strip()
        elif line.startswith("#"):
            continue  # other directives (#EXTM3U, #KODIPROP, etc.) — not needed downstream
        else:
            if not pending:
                continue
            channels.append(
                Channel(
                    name=name or tvg_id or "Unknown",
                    url=line,
                    tvg_id=tvg_id,
                    tvg_logo=tvg_logo,
                    group=group or ext_group,
                    source_ref=source_ref,
                    extra_attrs=extra,
                )
            )
            name = tvg_id = tvg_logo = group = ext_group = ""
            extra = {}
            pending = False
    return channels


def serialize_m3u(channels: list[Channel]) -> str:
    body = "\n".join(c.to_extinf() for c in channels)
    return f"#EXTM3U\n{body}\n" if body else "#EXTM3U\n"
