#!/bin/bash
# udev-notify.sh — Check if a newly connected device has an available driver
# in the Big Driver Manager database and show a dialog to the user.
#
# Called by the udev rule via systemd-run (runs as root). Finds the active
# graphical session and launches the GTK dialog as that user.
# Uses a pre-built cache file for fast lookups (~1ms).

set -euo pipefail

readonly CACHE_FILE="${BDM_CACHE_FILE:-/var/cache/big-driver-manager/ids_cache.txt}"
readonly DIALOG_SCRIPT="${BDM_DIALOG_SCRIPT:-/usr/share/big-driver-manager/udev-driver-dialog.py}"
readonly RUNTIME_BASE="${RUNTIME_DIRECTORY:-${BDM_RUNTIME_DIR:-/run/big-driver-manager}}"
readonly STATE_DIR="${RUNTIME_BASE}/notify-state"
readonly GLOBAL_LOCK_FILE="${RUNTIME_BASE}/notify.lock"
readonly COOLDOWN="${BDM_COOLDOWN:-30}"  # seconds between notifications for the same device
# Global cap: how many dialogs can be open concurrently for a session.
# Matches login-check-drivers.sh MAX_DIALOGS so hotplug storms (hub plug)
# don't flood the user.
readonly MAX_CONCURRENT="${BDM_MAX_CONCURRENT:-3}"
readonly CONCURRENT_FILE="${RUNTIME_BASE}/concurrent"
readonly PACMAN_BIN="${BDM_PACMAN_BIN:-pacman}"
readonly LOGINCTL_BIN="${BDM_LOGINCTL_BIN:-loginctl}"
readonly SYSTEMD_RUN_BIN="${BDM_SYSTEMD_RUN_BIN:-systemd-run}"
readonly PYTHON_BIN="${BDM_PYTHON_BIN:-python3}"

# Arguments from udev rule
BUS="${1:-}"        # "usb" or "pci"
VENDOR="${2:-}"     # vendor ID (hex)
DEVICE="${3:-}"     # device/product ID (hex)

[[ -z "$BUS" || -z "$VENDOR" || -z "$DEVICE" ]] && exit 0

# Normalize to uppercase, remove 0x prefix
VENDOR="${VENDOR^^}"
DEVICE="${DEVICE^^}"
VENDOR="${VENDOR#0X}"
DEVICE="${DEVICE#0X}"

SEARCH_ID="${VENDOR}:${DEVICE}"

# Ensure cache and dialog script exist
[[ -f "$CACHE_FILE" ]] || exit 0
[[ -f "$DIALOG_SCRIPT" ]] || exit 0

# Create a root-owned runtime directory in /run, never in a world-writable path.
install -d -m 0755 "$RUNTIME_BASE" "$STATE_DIR"
exec 9>"$GLOBAL_LOCK_FILE"
flock 9

# Fast lookup in the pre-built cache (~1ms for ~1400 lines)
# Cache format: VID:DID<TAB>category<TAB>driver_name<TAB>package<TAB>description
MATCH=$(grep -m1 -F "$SEARCH_ID" "$CACHE_FILE" 2>/dev/null || true)
[[ -z "$MATCH" ]] && exit 0

# Parse the match
IFS=$'\t' read -r _id CATEGORY DRIVER_NAME PACKAGE DESCRIPTION <<< "$MATCH"

# Check if the package is already installed
"$PACMAN_BIN" -Qq "$PACKAGE" &>/dev/null && exit 0

# Rate-limit: avoid duplicate dialogs for the same device
STATE_FILE="${STATE_DIR}/${SEARCH_ID//:/_}"
if [[ -f "$STATE_FILE" ]]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$STATE_FILE" 2>/dev/null || echo 0) ))
    [[ $LOCK_AGE -lt $COOLDOWN ]] && exit 0
fi

# Global concurrency cap: count recently-created state files (within the
# current session-ish window of 5 minutes). If we're at the cap, skip.
recent_count=$(find "$STATE_DIR" -maxdepth 1 -type f -mmin -5 2>/dev/null | wc -l)
if [[ "$recent_count" -ge "$MAX_CONCURRENT" ]]; then
    exit 0
fi

touch "$STATE_FILE"
# Maintain a small counter file for observability.
printf '%s\n' "$recent_count" > "$CONCURRENT_FILE" 2>/dev/null || true

# Find active graphical session and launch dialog as that user
while IFS= read -r session_id; do
    [[ -z "$session_id" ]] && continue

    SESSION_USER=$("$LOGINCTL_BIN" show-session "$session_id" -p Name --value 2>/dev/null || true)
    SESSION_TYPE=$("$LOGINCTL_BIN" show-session "$session_id" -p Type --value 2>/dev/null || true)
    SESSION_STATE=$("$LOGINCTL_BIN" show-session "$session_id" -p State --value 2>/dev/null || true)

    # Only target graphical sessions that are active
    [[ "$SESSION_TYPE" == "x11" || "$SESSION_TYPE" == "wayland" ]] || continue
    [[ "$SESSION_STATE" == "active" ]] || continue
    [[ -n "$SESSION_USER" ]] || continue

    USER_ID=$(id -u "$SESSION_USER" 2>/dev/null || true)
    [[ -n "$USER_ID" ]] || continue

    # Get display info for Wayland/X11
    DISPLAY_VAR=$("$LOGINCTL_BIN" show-session "$session_id" -p Display --value 2>/dev/null || true)
    WAYLAND_DISPLAY_VAR=$("$LOGINCTL_BIN" show-session "$session_id" -p WaylandDisplay --value 2>/dev/null || true)

    USER_HOME=$(getent passwd "$SESSION_USER" 2>/dev/null | cut -d: -f6)
    [[ -n "$USER_HOME" ]] || continue

    # Launch the GTK dialog as the session user via systemd-run
    # (sudo -u does not reliably grant access to the Wayland socket)
    "$SYSTEMD_RUN_BIN" --no-block --collect \
        --uid="$USER_ID" --gid="$(id -g "$SESSION_USER")" \
        --setenv=HOME="$USER_HOME" \
        --setenv=DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${USER_ID}/bus" \
        --setenv=XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
        --setenv=XDG_CONFIG_HOME="${USER_HOME}/.config" \
        --setenv=DISPLAY="${DISPLAY_VAR:-:0}" \
        --setenv=WAYLAND_DISPLAY="${WAYLAND_DISPLAY_VAR:-wayland-0}" \
        "$PYTHON_BIN" "$DIALOG_SCRIPT" \
            "$BUS" "$VENDOR" "$DEVICE" "$CATEGORY" "$DRIVER_NAME" "$PACKAGE" "$DESCRIPTION"
    break  # Only show on the first active graphical session

done < <("$LOGINCTL_BIN" list-sessions --no-legend 2>/dev/null | awk '{print $1}')

# Clean old state files (>5 min) from the protected runtime directory.
find "$STATE_DIR" -mindepth 1 -maxdepth 1 -type f -mmin +5 -delete 2>/dev/null || true
