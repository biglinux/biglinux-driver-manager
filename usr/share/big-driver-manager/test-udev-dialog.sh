#!/bin/bash
# test-udev-dialog.sh — Simulate the udev driver-available dialog for a device.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIR
readonly ASSETS_DIR="${BDM_ASSETS_DIR:-${SCRIPT_DIR}/assets}"
readonly CACHE_FILE="${BDM_CACHE_FILE:-/var/cache/big-driver-manager/ids_cache.txt}"
readonly FW_CACHE_FILE="${BDM_FW_CACHE_FILE:-/var/cache/big-driver-manager/firmware_cache.txt}"
readonly DIALOG_SCRIPT="${BDM_DIALOG_SCRIPT:-${SCRIPT_DIR}/udev-driver-dialog.py}"
readonly PYTHON_BIN="${BDM_PYTHON_BIN:-python3}"

usage() {
    cat <<'EOF'
Usage:
  test-udev-dialog.sh BUS VID:DID
  test-udev-dialog.sh BUS VID DID
  test-udev-dialog.sh firmware PACKAGE

Examples:
  test-udev-dialog.sh usb 0bda:b82c
  test-udev-dialog.sh usb 0bda:885a
  test-udev-dialog.sh pci 14e4:0576
  test-udev-dialog.sh sdio 024c:8179
  test-udev-dialog.sh usb 04f9:0042
  test-udev-dialog.sh firmware facetimehd-firmware

BUS can be: usb, pci, sdio, firmware
EOF
}

normalize_hex() {
    local value="${1^^}"
    value="${value#0X}"
    printf '%s' "$value"
}

read_text_file() {
    local path="$1"
    local fallback="$2"
    if [[ ! -f "$path" ]]; then
        printf '%s' "$fallback"
        return
    fi

    tr '\n' ' ' < "$path" | sed 's/[[:space:]]\+/ /g;s/^ //;s/ $//'
}

lookup_in_cache() {
    local search_id="$1"
    local match

    [[ -f "$CACHE_FILE" ]] || return 1

    match=$(awk -F $'\t' -v id="$search_id" '$1 == id { print; exit }' "$CACHE_FILE" 2>/dev/null || true)
    [[ -n "$match" ]] || return 1

    IFS=$'\t' read -r _id CATEGORY DRIVER_NAME PACKAGE DESCRIPTION <<< "$match"
    [[ -n "$CATEGORY" && -n "$DRIVER_NAME" && -n "$PACKAGE" ]] || return 1
    return 0
}

ids_filename_for_bus() {
    case "$1" in
        usb) printf 'usb.ids' ;;
        pci) printf 'pci.ids' ;;
        sdio) printf 'sdio.ids' ;;
        *) return 1 ;;
    esac
}

lookup_in_device_ids_assets() {
    local bus="$1"
    local search_id="$2"
    local ids_filename
    local driver_dir
    local ids_path
    local line
    local token

    ids_filename="$(ids_filename_for_bus "$bus")" || return 1

    for driver_dir in "$ASSETS_DIR"/device-ids/*/; do
        [[ -d "$driver_dir" ]] || continue
        ids_path="${driver_dir}${ids_filename}"
        [[ -f "$ids_path" ]] || continue

        while IFS= read -r line; do
            token="${line%%#*}"
            token="${token//[[:space:]]/}"
            token="${token^^}"
            [[ -z "$token" ]] && continue
            [[ "$token" == *:* ]] || continue
            [[ "$token" == "$search_id" ]] || continue

            DRIVER_NAME="$(basename "$driver_dir")"
            CATEGORY="device-ids"
            PACKAGE="$(read_text_file "${driver_dir}pkg" "$DRIVER_NAME")"
            DESCRIPTION="$(read_text_file "${driver_dir}description" "$DRIVER_NAME")"
            [[ -n "$PACKAGE" ]] || PACKAGE="$DRIVER_NAME"
            [[ -n "$DESCRIPTION" ]] || DESCRIPTION="$DRIVER_NAME"
            return 0
        done < "$ids_path"
    done

    return 1
}

lookup_in_peripherals_assets() {
    local kind="$1"
    local search_id="$2"
    local driver_dir
    local ids_path
    local line
    local token

    for driver_dir in "$ASSETS_DIR"/"$kind"/*/; do
        [[ -d "$driver_dir" ]] || continue
        ids_path="${driver_dir}usb.ids"
        [[ -f "$ids_path" ]] || continue

        while IFS= read -r line; do
            token="${line%%#*}"
            token="${token//[[:space:]]/}"
            token="${token^^}"
            [[ -z "$token" ]] && continue
            [[ "$token" == *:* ]] || continue
            [[ "$token" == "$search_id" ]] || continue

            DRIVER_NAME="$(basename "$driver_dir")"
            CATEGORY="$kind"
            PACKAGE="$DRIVER_NAME"
            DESCRIPTION="$(read_text_file "${driver_dir}description" "$DRIVER_NAME")"
            [[ -n "$DESCRIPTION" ]] || DESCRIPTION="$DRIVER_NAME"
            return 0
        done < "$ids_path"
    done

    return 1
}

lookup_firmware_in_cache() {
    local package="$1"
    local match
    local _firmware_path
    local _package
    local description_from_cache

    [[ -f "$FW_CACHE_FILE" ]] || return 1

    match=$(awk -F $'\t' -v pkg="$package" '$2 == pkg { print; exit }' "$FW_CACHE_FILE" 2>/dev/null || true)
    [[ -n "$match" ]] || return 1

    IFS=$'\t' read -r _firmware_path _package description_from_cache <<< "$match"

    CATEGORY="firmware"
    DRIVER_NAME="$package"
    PACKAGE="$package"
    DESCRIPTION="${description_from_cache:-$package}"
    return 0
}

lookup_firmware_in_assets() {
    local package="$1"
    local firmware_dir="$ASSETS_DIR/firmware/$package"

    [[ -d "$firmware_dir" ]] || return 1

    CATEGORY="firmware"
    DRIVER_NAME="$package"
    PACKAGE="$package"
    DESCRIPTION="$(read_text_file "${firmware_dir}/description" "$package")"
    [[ -n "$DESCRIPTION" ]] || DESCRIPTION="$package"
    return 0
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ $# -lt 2 ]]; then
    usage >&2
    exit 1
fi

BUS="${1,,}"
shift

case "$BUS" in
    usb | pci | sdio | firmware) ;;
    *)
        echo "Error: invalid BUS '$BUS'. Use usb, pci, sdio or firmware." >&2
        usage >&2
        exit 1
        ;;
esac

if [[ "$BUS" == "firmware" ]]; then
    if [[ $# -ne 1 ]]; then
        usage >&2
        exit 1
    fi
    FIRMWARE_PACKAGE="$1"
    shift
    VENDOR="0000"
    DEVICE="0000"
    SEARCH_ID="0000:0000"
else
    if [[ "$1" == *:* ]]; then
        VENDOR_RAW="${1%%:*}"
        DEVICE_RAW="${1##*:}"
        shift
    else
        if [[ $# -lt 2 ]]; then
            usage >&2
            exit 1
        fi
        VENDOR_RAW="$1"
        DEVICE_RAW="$2"
        shift 2
    fi

    VENDOR="$(normalize_hex "$VENDOR_RAW")"
    DEVICE="$(normalize_hex "$DEVICE_RAW")"
    SEARCH_ID="${VENDOR}:${DEVICE}"
fi

if [[ $# -gt 0 ]]; then
    echo "Error: unexpected extra arguments: $*" >&2
    usage >&2
    exit 1
fi

if [[ ! -f "$DIALOG_SCRIPT" ]]; then
    echo "Error: dialog script not found: $DIALOG_SCRIPT" >&2
    exit 1
fi

CATEGORY=""
DRIVER_NAME=""
PACKAGE=""
DESCRIPTION=""

if [[ "$BUS" == "firmware" ]]; then
    if lookup_firmware_in_cache "$FIRMWARE_PACKAGE"; then
        :
    elif lookup_firmware_in_assets "$FIRMWARE_PACKAGE"; then
        :
    else
        echo "No matching firmware package found: ${FIRMWARE_PACKAGE}" >&2
        exit 2
    fi
elif lookup_in_cache "$SEARCH_ID"; then
    :
elif lookup_in_device_ids_assets "$BUS" "$SEARCH_ID"; then
    :
elif [[ "$BUS" == "usb" ]] && lookup_in_peripherals_assets "printer" "$SEARCH_ID"; then
    :
elif [[ "$BUS" == "usb" ]] && lookup_in_peripherals_assets "scanner" "$SEARCH_ID"; then
    :
else
    echo "No matching driver entry found for ${BUS}:${SEARCH_ID}" >&2
    exit 2
fi

printf 'Simulating device %s %s\n' "$BUS" "$SEARCH_ID"
printf 'Using %s (%s)\n' "$DRIVER_NAME" "$PACKAGE"

exec "$PYTHON_BIN" "$DIALOG_SCRIPT" \
    "$BUS" "$VENDOR" "$DEVICE" "$CATEGORY" "$DRIVER_NAME" "$PACKAGE" "$DESCRIPTION"
