#!/bin/bash
# build-ids-cache.sh — Build the unified device-ID cache for fast udev lookups.
#
# Output format (tab-separated):
# VID:DID<TAB>category<TAB>driver_name<TAB>package<TAB>description
#
# Called by pkgbuild.install post_install/post_upgrade hooks.

set -euo pipefail

readonly ASSETS_DIR="${1:-/usr/share/big-driver-manager/assets}"
readonly CACHE_DIR="/var/cache/big-driver-manager"
readonly CACHE_FILE="${CACHE_DIR}/ids_cache.txt"
readonly FW_CACHE_FILE="${CACHE_DIR}/firmware_cache.txt"

mkdir -p "$CACHE_DIR"

# Temporary file for atomic write
TMPFILE=$(mktemp "${CACHE_DIR}/.ids_cache.XXXXXX")
trap 'rm -f "$TMPFILE"' EXIT

{
# Process device-ids (pci.ids, usb.ids, sdio.ids)
if [[ -d "${ASSETS_DIR}/device-ids" ]]; then
    for driver_dir in "${ASSETS_DIR}/device-ids"/*/; do
        [[ -d "$driver_dir" ]] || continue
        drv_name=$(basename "$driver_dir")
        drv_pkg=$(cat "${driver_dir}/pkg" 2>/dev/null || echo "$drv_name")
        drv_pkg="${drv_pkg%%[[:space:]]}"
        drv_pkg="${drv_pkg##[[:space:]]}"
        drv_desc=$(cat "${driver_dir}/description" 2>/dev/null || echo "$drv_name")
        drv_desc="${drv_desc%%[[:space:]]}"

        for ids_file in "${driver_dir}"/*.ids; do
            [[ -f "$ids_file" ]] || continue
            fname=$(basename "$ids_file")
            # Skip vendor-only files
            [[ "$fname" == "usb_vendors.ids" ]] && continue

            while IFS= read -r line; do
                line="${line%%#*}"          # strip comments
                line="${line// /}"          # strip spaces
                [[ -z "$line" ]] && continue
                [[ "$line" == *:* ]] || continue
                printf '%s\t%s\t%s\t%s\t%s\n' \
                    "${line^^}" "device-ids" "$drv_name" "$drv_pkg" "$drv_desc"
            done < "$ids_file"
        done
    done
fi

# Process printers and scanners (usb.ids only, not usb_vendors.ids)
for category in printer scanner; do
    if [[ -d "${ASSETS_DIR}/${category}" ]]; then
        for driver_dir in "${ASSETS_DIR}/${category}"/*/; do
            [[ -d "$driver_dir" ]] || continue
            drv_name=$(basename "$driver_dir")
            drv_desc=$(cat "${driver_dir}/description" 2>/dev/null || echo "$drv_name")
            drv_desc="${drv_desc%%[[:space:]]}"

            ids_file="${driver_dir}/usb.ids"
            [[ -f "$ids_file" ]] || continue

            while IFS= read -r line; do
                line="${line%%#*}"
                line="${line// /}"
                [[ -z "$line" ]] && continue
                [[ "$line" == *:* ]] || continue
                printf '%s\t%s\t%s\t%s\t%s\n' \
                    "${line^^}" "$category" "$drv_name" "$drv_name" "$drv_desc"
            done < "$ids_file"
        done
    fi
done
} > "$TMPFILE"

# Atomic replace
mv -f "$TMPFILE" "$CACHE_FILE"
chmod 644 "$CACHE_FILE"

LINES=$(wc -l < "$CACHE_FILE")
echo "Big Driver Manager: device ID cache built (${LINES} entries)"

# ─── Firmware cache ───
# Format: firmware_path<TAB>package<TAB>description
# firmware_path is relative to /usr/lib/firmware/ (what dmesg shows)
TMPFILE_FW=$(mktemp "${CACHE_DIR}/.fw_cache.XXXXXX")
trap 'rm -f "$TMPFILE_FW"' EXIT

{
if [[ -d "${ASSETS_DIR}/firmware" ]]; then
    for fw_dir in "${ASSETS_DIR}/firmware"/*/; do
        [[ -d "$fw_dir" ]] || continue
        pkg=$(basename "$fw_dir")
        fw_list="${fw_dir}/${pkg}"
        [[ -f "$fw_list" ]] || continue

        desc=$(cat "${fw_dir}/description" 2>/dev/null | tr '\n' ' ' | sed 's/  */ /g;s/ *$//' || echo "$pkg")

        while IFS= read -r fwpath; do
            fwpath="${fwpath%%[[:space:]]}"
            fwpath="${fwpath##[[:space:]]}"
            [[ -z "$fwpath" ]] && continue
            # Strip /usr/lib/firmware/ prefix to get the relative path
            rel="${fwpath#/usr/lib/firmware/}"
            # Skip non-kernel firmware (e.g. cura stuff in /usr/share/)
            [[ "$rel" == "$fwpath" ]] && continue
            printf '%s\t%s\t%s\n' "$rel" "$pkg" "$desc"
        done < "$fw_list"
    done
fi
} > "$TMPFILE_FW"

mv -f "$TMPFILE_FW" "$FW_CACHE_FILE"
chmod 644 "$FW_CACHE_FILE"

FW_LINES=$(wc -l < "$FW_CACHE_FILE")
echo "Big Driver Manager: firmware cache built (${FW_LINES} entries)"
