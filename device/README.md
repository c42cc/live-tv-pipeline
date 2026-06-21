# Appliance (device) — NVIDIA Shield "shield-parents"

The content-neutral box that renders the grid. It points at exactly one URL
forever (Invariant 0) and is otherwise a clean, capable Android TV.

## Identity

- Device: NVIDIA Shield TV Pro 2019 (`mdarcy`), Android 11 (SDK 30)
- Google account: `c42homenet@gmail.com` (creds in `ucs2/.env`)
- Local ADB: `10.0.0.62:5555` (Developer options -> Network debugging)
- Over Tailscale (once joined): `shield-parents` (magicDNS)

## Installed (pinned)

- TiviMate `5.3.2` (`ar.tvplayer.tv`) — the live-TV grid, points at the playlist URL
- FLauncher `0.18.0` (`me.efesser.flauncher`) — clean Home (stock launcher disabled)
- droidVNC-NG `2.20.0` (`net.christianbeier.droidvnc_ng`) — remote screen, port 5900, start-on-boot
- TV Bro `2.1.6` (`com.phlox.tvwebbrowser`) — TV browser w/ built-in content blocking
- Tailscale `1.98.4` (`com.tailscale.ipn`) — management mesh
- Kept consumer apps: Netflix, Prime Video, YouTube, Plex
- Removed: Vudu, Amazon Music, Play Games, Google TV/Movies, YouTube Music, Plex media server

## Ad-blocking (the primitive, not a per-app extension)

System-wide via **Private DNS** = `dns.adguard-dns.com` (DoT). Blocks ads/trackers
in every app, and follows the device to any network. TV Bro adds page-level blocking.

## Two planes (Invariant 2)

- **Content**: stream bytes go direct to the public internet (never via Tailscale).
- **Management**: VNC (5900) + ADB (5555) ride Tailscale only; never port-forwarded.

## Remote in (from a Mac on the tailnet)

```bash
# screen view + control
vncdotool -s shield-parents::5900 --password "$SHIELD_VNC_PASSWORD" capture /tmp/tv.png   # headless check
open vnc://shield-parents:5900        # interactive (macOS Screen Sharing)
# admin / push
adb connect shield-parents:5555 && scrcpy
```

## Rebuild

`ADB_ADDR=<addr> ./rebuild.sh` re-applies every deterministic step; it prints the
few interactive steps (Google sign-in, Network-debugging toggle, TiviMate URL,
VNC password, Tailscale approval) that cannot be done headlessly.

## Verified on this build

- TiviMate fetched the published URL -> 2415 channels parsed -> live video played
  on the panel (confirmed by remote screencap).
- droidVNC capture worked over the network with password auth (Screen Capturing,
  Input, Start-on-Boot all GRANTED).
- Pipeline CI (GitHub Actions) built + validated + published green in 5m28s.
