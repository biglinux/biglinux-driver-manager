#!/bin/bash
# udev-notify.sh — Check if a newly connected device has an available driver
# in the Big Driver Manager database and show a dialog to the user.
#
# Called by the udev rule via systemd-run (runs as root). Finds the active
# graphical session and launches the GTK dialog as that user.
# Uses a pre-built cache file for fast lookups (~1ms).

set -euo pipefail

readonly CACHE_FILE="/var/cache/big-driver-manager/ids_cache.txt"
readonly DIALOG_SCRIPT="/usr/share/big-driver-manager/udev-driver-dialog.py"
readonly LOCK_DIR="/tmp/bkm-udev-notify"
readonly COOLDOWN=30  # seconds between notifications for the same device

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

# Fast lookup in the pre-built cache (~1ms for ~1400 lines)
# Cache format: VID:DID<TAB>category<TAB>driver_name<TAB>package<TAB>description
MATCH=$(grep -m1 -F "$SEARCH_ID" "$CACHE_FILE" 2>/dev/null || true)
[[ -z "$MATCH" ]] && exit 0

# Parse the match
IFS=$'\t' read -r _id CATEGORY DRIVER_NAME PACKAGE DESCRIPTION <<< "$MATCH"

# Check if the package is already installed
pacman -Qq "$PACKAGE" &>/dev/null && exit 0

# Rate-limit: avoid duplicate dialogs for the same device
mkdir -p "$LOCK_DIR" 2>/dev/null || true
LOCK_FILE="${LOCK_DIR}/${SEARCH_ID//:/}"
if [[ -f "$LOCK_FILE" ]]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0) ))
    [[ $LOCK_AGE -lt $COOLDOWN ]] && exit 0
fi
touch "$LOCK_FILE" 2>/dev/null || true

# Find active graphical session and launch dialog as that user
while IFS= read -r session_id; do
    [[ -z "$session_id" ]] && continue

    SESSION_USER=$(loginctl show-session "$session_id" -p Name --value 2>/dev/null || true)
    SESSION_TYPE=$(loginctl show-session "$session_id" -p Type --value 2>/dev/null || true)
    SESSION_STATE=$(loginctl show-session "$session_id" -p State --value 2>/dev/null || true)

    # Only target graphical sessions that are active
    [[ "$SESSION_TYPE" == "x11" || "$SESSION_TYPE" == "wayland" ]] || continue
    [[ "$SESSION_STATE" == "active" ]] || continue
    [[ -n "$SESSION_USER" ]] || continue

    USER_ID=$(id -u "$SESSION_USER" 2>/dev/null || true)
    [[ -n "$USER_ID" ]] || continue

    # Get display info for Wayland/X11
    DISPLAY_VAR=$(loginctl show-session "$session_id" -p Display --value 2>/dev/null || true)
    WAYLAND_DISPLAY_VAR=$(loginctl show-session "$session_id" -p WaylandDisplay --value 2>/dev/null || true)

    USER_HOME=$(eval echo "~${SESSION_USER}")

    # Launch the GTK dialog as the session user via systemd-run
    # (sudo -u does not reliably grant access to the Wayland socket)
    systemd-run --no-block --collect \
        --uid="$USER_ID" --gid="$(id -g "$SESSION_USER")" \
        --setenv=HOME="$USER_HOME" \
        --setenv=DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${USER_ID}/bus" \
        --setenv=XDG_RUNTIME_DIR="/run/user/${USER_ID}" \
        --setenv=XDG_CONFIG_HOME="${USER_HOME}/.config" \
        --setenv=DISPLAY="${DISPLAY_VAR:-:0}" \
        --setenv=WAYLAND_DISPLAY="${WAYLAND_DISPLAY_VAR:-wayland-0}" \
        python3 "$DIALOG_SCRIPT" \
            "$BUS" "$VENDOR" "$DEVICE" "$CATEGORY" "$DRIVER_NAME" "$PACKAGE" "$DESCRIPTION"
    break  # Only show on the first active graphical session

done < <(loginctl list-sessions --no-legend 2>/dev/null | awk '{print $1}')

# Clean old lock files (>5 min)
find "$LOCK_DIR" -maxdepth 1 -type f -mmin +5 -delete 2>/dev/null || true
