"""Preflight: refuse to run on a broken instrument. Every check returns the exact
one-command fix. A missing dep HALTS — we never 'skip validation if ffprobe is
absent', because a build that didn't validate must never masquerade as one that did."""

from __future__ import annotations

import shutil
import subprocess

from . import PipelineError
from .config import DIST_DIR, STATE_PATH


def _runnable(cmd: list[str]) -> bool:
    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def preflight() -> None:
    checks: list[tuple[bool, str, str]] = []

    ff = shutil.which("ffprobe") is not None and _runnable(["ffprobe", "-version"])
    checks.append((ff, "ffprobe (stream liveness probe)", "brew install ffmpeg  # or apt-get install -y ffmpeg"))

    yt = shutil.which("yt-dlp") is not None and _runnable(["yt-dlp", "--version"])
    checks.append((yt, "yt-dlp (website stream resolver)", "brew install yt-dlp  # or pipx install yt-dlp"))

    try:
        import yaml  # noqa: F401
        import requests  # noqa: F401
        deps_ok = True
    except ImportError:
        deps_ok = False
    checks.append((deps_ok, "python deps (pyyaml, requests)", "pip install -r requirements.txt"))

    try:
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        probe = DIST_DIR / ".writable"
        probe.write_text("ok")
        probe.unlink()
        write_ok = True
    except OSError:
        write_ok = False
    checks.append((write_ok, f"writable output dir ({DIST_DIR})", "check filesystem permissions"))

    broken = [(name, fix) for ok, name, fix in checks if not ok]
    if broken:
        lines = "\n".join(f"  - {name}\n      fix: {fix}" for name, fix in broken)
        raise PipelineError(f"preflight FAILED ({len(broken)} broken):\n{lines}")
