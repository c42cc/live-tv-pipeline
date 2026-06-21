# live-tv-pipeline

The **content plane** for the multi-country live-TV appliance. It turns one
human-edited manifest (`sources.yaml`) into one validated `playlist.m3u`
(+ `epg.xml.gz`) published at a stable URL that an NVIDIA Shield (running
TiviMate) fetches forever.

## The one idea (Invariant 0)

The appliance and the content graph are completely separate. The Shield points
at exactly one stable URL, permanently, and is content-neutral. **All** breadth,
churn, and curation live here, upstream, where they can change daily without ever
touching the box.

## Edit coverage = edit one file

Everything is `sources.yaml`:

- add a country -> one ISO code in `countries`
- add a category -> one keyword in `categories`
- add a channel -> one line in `channels_explicit`
- add a website stream -> one line in `website_sources` (resolved via yt-dlp)
- remove anything -> its tvg-id in `exclude.tvg_ids`

Commit, and the scheduled GitHub Action rebuilds + republishes with zero device
interaction.

## What a build does

1. **Fetch + merge** every declared upstream (iptv-org country/category lists),
   plus explicit channels.
2. **Resolve** each `website_source` to its current stream URL via `yt-dlp`.
3. **Dedupe** (by tvg-id, else URL) + **normalize** group titles + apply excludes.
4. **Validate** every candidate with an `ffprobe` liveness probe, carrying a
   rolling *last-seen-alive* history so one bad day never nukes a real channel
   (`state/last_seen.json`); prune only after N consecutive failures.
5. **Emit** `dist/playlist.m3u`, `dist/epg.xml.gz`, and `dist/report.json`
   (the observability surface), then commit them so the raw URL is fresh.

## Run it locally

```bash
make install     # one-time: venv + deps
make smoke       # fast: caps candidates, finishes in seconds
make build       # full: validates every declared stream
make verify      # acceptance: re-probes a random sample of the EMITTED playlist
```

## Doctrine

- **No silent fallbacks.** A broken dependency or malformed manifest is a typed
  `PipelineError` that halts. Expected *content* churn (a dead stream) is recorded
  in `report.json` and governed by the last-seen history — visible, never hidden.
- **One fact, one home.** The validator's result directly governs what is emitted;
  there is no separate reconciler keeping two copies in sync.
- **Failures are ours.** A flaky upstream, a timeout, a delay — all surfaced in the
  report and the heartbeat, never blamed on a third party.

## Published URL

After the first successful Action run, the appliance points at:

```
playlist: https://raw.githubusercontent.com/<owner>/live-tv-pipeline/main/dist/playlist.m3u
epg:      https://raw.githubusercontent.com/<owner>/live-tv-pipeline/main/dist/epg.xml.gz
```
