#!/bin/bash
# login-check-drivers.sh — Scan present hardware and notify about available
# drivers that are not yet installed.
#
# Runs as the logged-in user (via systemd user timer, ~90s after login).
# Reads the pre-built cache and compares against USB and PCI devices.

set -euo pipefail

readonly CACHE_FILE="${BDM_CACHE_FILE:-/var/cache/big-driver-manager/ids_cache.txt}"
readonly DIALOG_SCRIPT="${BDM_DIALOG_SCRIPT:-/usr/share/big-driver-manager/udev-driver-dialog.py}"
readonly BLACKLIST_FILE="${BDM_BLACKLIST_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/big-driver-manager/ignored_devices.json}"
readonly SHOWN_FILE="${BDM_SHOWN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/big-driver-manager/login_check_shown}"
readonly MAX_DIALOGS="${BDM_MAX_DIALOGS:-3}"  # Don't overwhelm the user
readonly PACMAN_BIN="${BDM_PACMAN_BIN:-pacman}"
readonly PYTHON_BIN="${BDM_PYTHON_BIN:-python3}"
readonly LSPCI_BIN="${BDM_LSPCI_BIN:-lspci}"
readonly DMESG_BIN="${BDM_DMESG_BIN:-dmesg}"
readonly USB_SYSFS="${BDM_USB_SYSFS:-/sys/bus/usb/devices}"

[[ -f "$CACHE_FILE" ]] || exit 0
[[ -f "$DIALOG_SCRIPT" ]] || exit 0

# Avoid showing the same batch of dialogs repeatedly within the same session.
# The shown file is cleaned on each fresh login by the timer's OnStartupSec trigger.
if [[ -f "$SHOWN_FILE" ]]; then
    SHOWN_AGE=$(( $(date +%s) - $(stat -c %Y "$SHOWN_FILE" 2>/dev/null || echo 0) ))
    # If shown less than 1 hour ago, skip
    [[ $SHOWN_AGE -lt 3600 ]] && exit 0
fi

# Load blacklist into an associative array for O(1) lookups. Entries look
# like "VENDOR:DEVICE" or "fw:<package-name>".
declare -A BLACKLIST_SET=()
if [[ -f "$BLACKLIST_FILE" ]]; then
    while IFS= read -r entry; do
        [[ -n "$entry" ]] && BLACKLIST_SET["$entry"]=1
    done < <(BLACKLIST_PATH="$BLACKLIST_FILE" "$PYTHON_BIN" -c '
import json
import os
import sys
try:
    with open(os.environ["BLACKLIST_PATH"], encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, str) and entry:
                print(entry)
except Exception:
    sys.exit(0)
' 2>/dev/null || true)
fi

# Collect present USB and PCI IDs, remembering which devices already have a
# kernel driver bound (those need no extra driver).
declare -A ALL_IDS
declare -A HAS_DRIVER

for dev in "$USB_SYSFS"/*/idVendor; do
    dir="${dev%/idVendor}"
    vid=$(cat "$dev" 2>/dev/null || true)
    pid=$(cat "$dir/idProduct" 2>/dev/null || true)
    [[ -n "$vid" && -n "$pid" ]] || continue
    id="${vid^^}:${pid^^}"
    ALL_IDS["$id"]="usb"
    for drv in "$dir"/*:*/driver; do
        [[ -e "$drv" ]] || continue
        [[ "$(basename "$(readlink -f "$drv")")" == "usbfs" ]] && continue
        HAS_DRIVER["$id"]=1
        break
    done
done

# lspci -nk output:
#   00:02.0 0300: 8086:5917 (rev 04)
#   \tKernel driver in use: i915
pci_id=""
while IFS= read -r line; do
    if [[ "$line" != [[:space:]]* ]]; then
        pci_id=$(grep -oP '\b[0-9a-fA-F]{4}:[0-9a-fA-F]{4}\b' <<< "$line" | head -1 || true)
        pci_id="${pci_id^^}"
        [[ -n "$pci_id" ]] && ALL_IDS["$pci_id"]="pci"
    elif [[ -n "$pci_id" && "$line" == *"Kernel driver in use:"* ]]; then
        HAS_DRIVER["$pci_id"]=1
    fi
done < <("$LSPCI_BIN" -nk 2>/dev/null || true)

# Build a grep pattern from all present IDs for fast cache lookup
ID_PATTERN=""
for id in "${!ALL_IDS[@]}"; do
    if [[ -n "$ID_PATTERN" ]]; then
        ID_PATTERN="${ID_PATTERN}|${id}"
    else
        ID_PATTERN="$id"
    fi
done

# Search cache for matches (grep is fast even with many alternations)
dialog_count=0
if [[ -n "$ID_PATTERN" ]]; then
    while IFS=$'\t' read -r cache_id category driver_name package description; do
        [[ $dialog_count -ge $MAX_DIALOGS ]] && break
        [[ -z "$cache_id" ]] && continue

        bus="${ALL_IDS[$cache_id]:-usb}"

        # Device already works with a built-in kernel driver?
        [[ "$category" == "device-ids" && -n "${HAS_DRIVER[$cache_id]:-}" ]] && continue

        # Already installed?
        "$PACMAN_BIN" -Qq "$package" &>/dev/null && continue

        # Blacklisted? O(1) lookup.
        [[ -n "${BLACKLIST_SET[$cache_id]+_}" ]] && continue

        vid="${cache_id%%:*}"
        did="${cache_id#*:}"

        # Launch dialog
        "$PYTHON_BIN" "$DIALOG_SCRIPT" "$bus" "$vid" "$did" "$category" "$driver_name" "$package" "$description" &
        dialog_count=$((dialog_count + 1))

        # Small delay between dialogs to avoid overlap
        sleep 2

    done < <(grep -E "^(${ID_PATTERN})" "$CACHE_FILE" || true)
fi

# ─── Firmware check via dmesg ───
readonly FW_CACHE="${BDM_FW_CACHE_FILE:-/var/cache/big-driver-manager/firmware_cache.txt}"

if [[ -f "$FW_CACHE" ]] && [[ $dialog_count -lt $MAX_DIALOGS ]]; then
    # Extract firmware names that failed to load
    MISSING_FW=$("$DMESG_BIN" 2>/dev/null | grep -oP 'Direct firmware load for \K\S+(?= failed)' | sort -u || true)

    if [[ -n "$MISSING_FW" ]]; then
        # Build grep pattern from missing firmware paths
        FW_PATTERN=$(echo "$MISSING_FW" | paste -sd'|')

        declare -A FW_SHOWN
        while IFS=$'\t' read -r fw_path package description; do
            [[ $dialog_count -ge $MAX_DIALOGS ]] && break
            [[ -z "$fw_path" ]] && continue
            [[ -n "${FW_SHOWN[$package]+_}" ]] && continue

            # Already installed?
            "$PACMAN_BIN" -Qq "$package" &>/dev/null && continue

            # Blacklisted? O(1) lookup.
            [[ -n "${BLACKLIST_SET["fw:$package"]+_}" ]] && continue

            FW_SHOWN["$package"]=1
            "$PYTHON_BIN" "$DIALOG_SCRIPT" "firmware" "0000" "0000" "firmware" "$package" "$package" "$description" &
            dialog_count=$((dialog_count + 1))
            sleep 2
        done < <(grep -E "^(${FW_PATTERN})" "$FW_CACHE" || true)
    fi
fi

# Mark as shown for this session
mkdir -p "$(dirname "$SHOWN_FILE")" 2>/dev/null || true
touch "$SHOWN_FILE"
