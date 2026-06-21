#!/usr/bin/env bash
# =============================================================================
# rebuild.sh — dead Shield -> working appliance, scripted (Invariant 3: cattle).
# =============================================================================
# Re-applies every DETERMINISTIC step done during the initial build via ADB.
# The few irreducible interactive steps (Google sign-in, enabling Network
# debugging, Tailscale tailnet approval, TiviMate playlist URL, VNC password)
# are printed at the end — they cannot be done headlessly by design.
#
# Usage:
#   ADB_ADDR=10.0.0.62:5555 ./rebuild.sh         # local network
#   ADB_ADDR=shield-parents:5555 ./rebuild.sh    # over Tailscale (magicDNS)
#
# Prereq: `adb` installed; the Shield reachable + already authorized for this Mac.
set -euo pipefail

ADB_ADDR="${ADB_ADDR:-10.0.0.62:5555}"
PLAYLIST_URL="https://raw.githubusercontent.com/c42cc/live-tv-pipeline/main/dist/playlist.m3u"
WORK="$(mktemp -d)"
S(){ adb -s "$ADB_ADDR" "$@"; }

# Pinned APK versions (captured from the verified build).
TVBRO="https://github.com/truefedex/tv-bro/releases/download/v2.1.6/tvbro-2.1.6-generic-geckoIncluded-arm64-v8a.apk"
TAILSCALE="https://github.com/tailscale/tailscale-android/releases/download/1.98.4-t9e69045b2-g0b6f6554d/tailscale-android-universal-1.98.4.apk"
FLAUNCHER="https://gitlab.com/api/v4/projects/26632151/packages/generic/flauncher/0.18.0/flauncher-0.18.0.apk"

echo ">> connecting to $ADB_ADDR"
adb connect "$ADB_ADDR" >/dev/null
S wait-for-device

echo ">> downloading + installing pinned APKs"
curl -fsSL -o "$WORK/tvbro.apk"     "$TVBRO"
curl -fsSL -o "$WORK/tailscale.apk" "$TAILSCALE"
curl -fsSL -o "$WORK/flauncher.apk" "$FLAUNCHER"
for a in flauncher tailscale tvbro; do S install -r "$WORK/$a.apk"; done
echo ">> NOTE: TiviMate (ar.tvplayer.tv) is a Play-Store install (free); install it from Play."

echo ">> system-wide ad-block: AdGuard Private DNS (network-independent)"
S shell settings put global private_dns_mode hostname
S shell settings put global private_dns_specifier dns.adguard-dns.com

echo ">> clean launcher: FLauncher as Home (disable stock launcher)"
S shell cmd package set-home-activity me.efesser.flauncher/me.efesser.flauncher.MainActivity || true
S shell pm disable-user --user 0 com.google.android.tvlauncher || true

echo ">> kill debug overlays; long display timeout"
S shell settings put system pointer_location 0
S shell settings put system show_touches 0
S shell settings put system screen_off_timeout 3600000

echo ">> declutter (idempotent): remove non-kept entertainment apps"
for pkg in air.com.vudu.air.DownloaderTablet com.amazon.music.tv com.google.android.play.games \
           com.google.android.videos com.google.android.youtube.tvmusic com.plexapp.mediaserver.smb; do
  S shell pm uninstall --user 0 "$pkg" >/dev/null 2>&1 || true
done

rm -rf "$WORK"
cat <<EOF

================ DETERMINISTIC SETUP DONE. Remaining manual steps =============
These cannot be done headlessly (by design):

1. Google account on the Shield: c42homenet@gmail.com  (see ucs2/.env)
2. Developer options -> Network debugging ON (enables this ADB channel).
3. TiviMate: install from Play, add M3U playlist URL:
     $PLAYLIST_URL
   (TV playlist -> Done; skip EPG.)
4. Tailscale: open app -> Get Started -> approve the device into the
   corbin.c.chase tailnet (QR/code), enable Always-on VPN. Do NOT set an exit
   node, do NOT block non-VPN traffic (Invariant 2: streams go direct).

Remote view+control (no on-device app needed): from a Mac on the tailnet,
   adb connect $ADB_ADDR && scrcpy --no-audio
==============================================================================
EOF
