"""Liveness validation + rolling 'last seen alive' history.

This is the reliability multiplier. The validator (catcher of dead streams) and
the emitter (producer of the playlist) are one pipeline: the probe result
directly governs what is emitted. There is no separate reconciler to keep two
copies in sync — there is one fact (is this stream alive?) with one home (state).
"""

from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import STATE_PATH, ValidatePolicy
from .models import Channel


@dataclass(slots=True)
class ProbeOutcome:
    channel: Channel
    alive: bool
    emitted: bool = False
    state: str = ""  # "alive" | "grace" | "pruned" | "dead-unknown"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def _probe(channel: Channel, timeout_s: int) -> bool:
    """True iff a real A/V stream answers within the timeout."""
    rw = str(timeout_s * 1_000_000)  # ffprobe wants microseconds
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-rw_timeout", rw,
                "-i", channel.url,
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s + 4,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    out = (proc.stdout or "").strip()
    return proc.returncode == 0 and ("video" in out or "audio" in out)


def validate_and_select(channels: list[Channel], policy: ValidatePolicy) -> tuple[list[ProbeOutcome], dict]:
    state = _load_state()
    now = _now()
    now_iso = now.isoformat()
    deadline = time.monotonic() + policy.time_budget_s

    alive_map: dict[int, bool] = {}
    with ThreadPoolExecutor(max_workers=policy.max_workers) as pool:
        futures = {pool.submit(_probe, c, policy.ffprobe_timeout_s): i for i, c in enumerate(channels)}
        for fut in as_completed(futures):
            i = futures[fut]
            if time.monotonic() > deadline:
                # Out of time budget: leave un-probed channels to their last-seen
                # status (recorded, not guessed). This is observable in the report.
                break
            try:
                alive_map[i] = fut.result()
            except Exception:  # a probe thread blew up — treat as not-alive, recorded
                alive_map[i] = False

    outcomes: list[ProbeOutcome] = []
    for i, c in enumerate(channels):
        probed = i in alive_map
        alive = alive_map.get(i, False)
        rec = state.get(c.key(), {"consecutive_failures": 0, "ever_alive": False, "last_alive": ""})

        if alive:
            rec["consecutive_failures"] = 0
            rec["ever_alive"] = True
            rec["last_alive"] = now_iso
        elif probed:
            rec["consecutive_failures"] = int(rec.get("consecutive_failures", 0)) + 1
        # if not probed (budget), leave the record untouched

        rec["name"] = c.name
        state[c.key()] = rec

        emitted, label = _decide(alive, probed, rec, policy, now)
        outcomes.append(ProbeOutcome(channel=c, alive=alive, emitted=emitted, state=label))

    _save_state(state)
    return outcomes, state


def _decide(alive: bool, probed: bool, rec: dict, policy: ValidatePolicy, now: datetime) -> tuple[bool, str]:
    if alive:
        return True, "alive"
    if not rec.get("ever_alive"):
        return False, "dead-unknown"  # never seen working -> never emit
    if int(rec.get("consecutive_failures", 0)) >= policy.prune_after_failures:
        return False, "pruned"
    last = rec.get("last_alive") or ""
    if last:
        try:
            age_days = (now - datetime.fromisoformat(last)).total_seconds() / 86400
            if age_days > policy.grace_days:
                return False, "pruned"
        except ValueError:
            pass
    return True, "grace"  # recently alive, under threshold -> keep, visibly, during grace
