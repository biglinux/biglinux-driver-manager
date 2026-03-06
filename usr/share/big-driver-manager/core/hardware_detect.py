#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Hardware Detection — detects PCI/USB/SDIO devices and matches them against
the driver database.  Also detects missing firmware via dmesg.

All detection runs in threads so the UI never blocks.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.driver_database import (
    DriverDatabase,
    DriverModule,
    FirmwareEntry,
    PeripheralEntry,
)
from core.logging_config import get_logger
from core.subprocess_env import subprocess_env

_logger = get_logger("HardwareDetect")


@dataclass
class DetectedDevice:
    """A hardware device found on the system."""

    bus: str  # "pci", "usb", "sdio"
    vendor_id: str
    device_id: str
    name: str
    device_type: str = ""
    driver_in_use: str = ""


def _run(args: list[str], timeout: int = 10) -> str:
    """Run a command and return stdout, empty string on error."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=subprocess_env(),
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        _logger.warning("Command %s failed: %s", args, exc)
        return ""


def detect_pci_devices() -> list[DetectedDevice]:
    """Detect PCI devices using lspci -knn (includes driver binding info)."""
    output = _run(["lspci", "-knn"])
    devices: list[DetectedDevice] = []
    # Line example: 00:02.0 VGA compatible controller [0300]: Intel Corp... [8086:5917]
    dev_pattern = re.compile(
        r"^\S+\s+(.+?)\s+\[[\da-fA-F]{4}\]:\s+(.+?)\s+\[([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\]",
    )
    drv_pattern = re.compile(r"^\s+Kernel driver in use:\s+(\S+)")
    current_dev: DetectedDevice | None = None
    for line in output.splitlines():
        m = dev_pattern.search(line)
        if m:
            current_dev = DetectedDevice(
                bus="pci",
                device_type=m.group(1).strip(),
                name=m.group(2).strip(),
                vendor_id=m.group(3).upper(),
                device_id=m.group(4).upper(),
            )
            devices.append(current_dev)
            continue
        if current_dev:
            dm = drv_pattern.match(line)
            if dm:
                current_dev.driver_in_use = dm.group(1)
    _logger.info("PCI devices detected: %d", len(devices))
    return devices


def detect_usb_devices() -> list[DetectedDevice]:
    """Detect USB devices using lsusb."""
    output = _run(["lsusb"])
    devices: list[DetectedDevice] = []
    # Line example: Bus 001 Device 003: ID 0bda:8178 Realtek Semiconductor Corp. RTL8192CU ...
    pattern = re.compile(
        r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.*)",
    )
    for line in output.splitlines():
        m = pattern.search(line)
        if m:
            devices.append(
                DetectedDevice(
                    bus="usb",
                    vendor_id=m.group(1).upper(),
                    device_id=m.group(2).upper(),
                    name=m.group(3).strip(),
                )
            )
    _logger.info("USB devices detected: %d", len(devices))
    return devices


def detect_sdio_devices() -> list[DetectedDevice]:
    """Detect SDIO devices from /sys/bus/sdio/devices/."""
    devices: list[DetectedDevice] = []
    sdio_base = Path("/sys/bus/sdio/devices")
    if not sdio_base.is_dir():
        return devices
    for entry in sdio_base.iterdir():
        vendor_file = entry / "vendor"
        device_file = entry / "device"
        if vendor_file.exists() and device_file.exists():
            vendor = vendor_file.read_text().strip().replace("0x", "").upper()
            device = device_file.read_text().strip().replace("0x", "").upper()
            devices.append(
                DetectedDevice(
                    bus="sdio",
                    vendor_id=vendor,
                    device_id=device,
                    name=entry.name,
                )
            )
    _logger.info("SDIO devices detected: %d", len(devices))
    return devices


def detect_all_devices() -> list[DetectedDevice]:
    """Detect all PCI, USB, and SDIO devices."""
    devices: list[DetectedDevice] = []
    devices.extend(detect_pci_devices())
    devices.extend(detect_usb_devices())
    devices.extend(detect_sdio_devices())
    return devices


def detect_missing_firmware() -> set[str]:
    """Parse dmesg for missing firmware file paths."""
    output = _run(["dmesg"], timeout=5)
    missing: set[str] = set()
    # Pattern: "firmware: failed to load X" or "Direct firmware load for X failed"
    patterns = [
        re.compile(r"firmware:\s+failed\s+to\s+load\s+(\S+)"),
        re.compile(r"Direct\s+firmware\s+load\s+for\s+(\S+)\s+failed"),
    ]
    for line in output.splitlines():
        for pat in patterns:
            m = pat.search(line)
            if m:
                fw_path = m.group(1)
                # Normalize to /usr/lib/firmware/ path
                if not fw_path.startswith("/"):
                    fw_path = f"/usr/lib/firmware/{fw_path}"
                missing.add(fw_path)
    _logger.info("Missing firmware entries: %d", len(missing))
    return missing


def check_installed_packages(
    packages: list[str],
    _installed_cache: set[str] | None = None,
) -> dict[str, bool]:
    """Check which packages are installed via pacman.

    Args:
        packages: package names to check.
        _installed_cache: pre-fetched set from ``fetch_installed_set()``.
            When provided the subprocess call is skipped entirely.
    """
    if not packages:
        return {}
    installed = (
        _installed_cache if _installed_cache is not None else fetch_installed_set()
    )
    return {pkg: pkg in installed for pkg in packages}


def fetch_installed_set() -> set[str]:
    """Run ``pacman -Qq`` once and return the set of installed package names."""
    output = _run(["pacman", "-Qq"], timeout=10)
    return set(output.splitlines())


def match_modules(
    database: DriverDatabase,
    devices: list[DetectedDevice] | None = None,
    installed_cache: set[str] | None = None,
) -> list[DriverModule]:
    """Match detected devices against the driver database modules.

    Updates each module's `detected`, `installed`, and `detected_device_name` fields.
    Updates `installed` for ALL modules, not just detected ones.
    Returns only modules that match at least one detected device.

    Args:
        installed_cache: pre-fetched set from ``fetch_installed_set()``.
    """
    if devices is None:
        devices = detect_all_devices()

    # Build lookup sets by bus type
    pci_ids = {(d.vendor_id, d.device_id): d for d in devices if d.bus == "pci"}
    usb_ids = {(d.vendor_id, d.device_id): d for d in devices if d.bus == "usb"}
    sdio_ids = {(d.vendor_id, d.device_id): d for d in devices if d.bus == "sdio"}

    detected_modules: list[DriverModule] = []
    all_packages = [m.package for m in database.modules if m.package]
    installed_map = check_installed_packages(all_packages, installed_cache)

    for module in database.modules:
        module.installed = installed_map.get(module.package, False)
        matched_device: DetectedDevice | None = None

        for vid, did in module.pci_ids:
            if (vid, did) in pci_ids:
                matched_device = pci_ids[(vid, did)]
                break

        if not matched_device:
            for vid, did in module.usb_ids:
                if (vid, did) in usb_ids:
                    matched_device = usb_ids[(vid, did)]
                    break

        if not matched_device:
            for vid, did in module.sdio_ids:
                if (vid, did) in sdio_ids:
                    matched_device = sdio_ids[(vid, did)]
                    break

        if matched_device:
            module.detected = True
            module.detected_device_name = matched_device.name
            module.device_has_driver = bool(matched_device.driver_in_use)
            detected_modules.append(module)

    _logger.info("Matched modules: %d", len(detected_modules))
    return detected_modules


def match_firmware(
    database: DriverDatabase,
    missing_fw: set[str] | None = None,
    installed_cache: set[str] | None = None,
) -> list[FirmwareEntry]:
    """Match missing firmware against the firmware database.

    Updates `detected` and `installed` for ALL firmware entries.
    Returns the complete list so the UI can show everything,
    highlighting detected ones.

    Args:
        installed_cache: pre-fetched set from ``fetch_installed_set()``.
    """
    if missing_fw is None:
        missing_fw = detect_missing_firmware()

    all_fw_packages = [fw.package for fw in database.firmware]
    installed_map = check_installed_packages(all_fw_packages, installed_cache)

    detected_count = 0
    for entry in database.firmware:
        entry.installed = installed_map.get(entry.package, False)
        entry.detected = False
        for fw_path in entry.firmware_files:
            if fw_path.strip() in missing_fw:
                entry.detected = True
                detected_count += 1
                break

    _logger.info(
        "Firmware: %d total, %d detected missing",
        len(database.firmware),
        detected_count,
    )
    return list(database.firmware)


def update_peripheral_install_status(
    database: DriverDatabase,
    installed_cache: set[str] | None = None,
) -> None:
    """Update installed and detected status for printers and scanners.

    Marks packages as ``installed`` via pacman and uses USB vendor-ID
    matching to set ``detected`` when a device from the same brand is
    connected (hybrid detection).

    Args:
        installed_cache: pre-fetched set from ``fetch_installed_set()``.
    """
    all_packages: list[str] = []
    all_packages.extend(p.package for p in database.printers)
    all_packages.extend(s.package for s in database.scanners)
    installed_map = check_installed_packages(all_packages, installed_cache)

    connected_vendors, connected_ids = _detect_usb_peripheral_ids()

    for p in database.printers:
        p.installed = installed_map.get(p.package, False)
        p.detected = _match_peripheral_vendor(p, connected_vendors, connected_ids)
    for s in database.scanners:
        s.installed = installed_map.get(s.package, False)
        s.detected = _match_peripheral_vendor(s, connected_vendors, connected_ids)

    det_p = sum(1 for p in database.printers if p.detected)
    det_s = sum(1 for s in database.scanners if s.detected)
    _logger.info(
        "Peripherals: printers=%d detected, scanners=%d detected",
        det_p,
        det_s,
    )


# USB Vendor IDs for common printer/scanner manufacturers.
_USB_VENDOR_BRANDS: dict[str, list[str]] = {
    "04F9": ["brother"],
    "04B8": ["epson", "iscan"],
    "04A9": ["canon", "cnijfilter", "scangearmp"],
    "03F0": ["hp", "hplip"],
    "04E8": ["samsung"],
    "22D9": ["pantum"],
    "0482": ["kyocera"],
    "05CA": ["ricoh"],
    "0924": ["xerox"],
    "043D": ["lexmark"],
    "132B": ["konica"],
    "413C": ["dell"],
}


def _detect_usb_peripheral_vendors() -> set[str]:
    """Return the set of USB vendor IDs for connected printers/scanners."""
    devices = detect_usb_devices()
    return {d.vendor_id for d in devices if d.vendor_id in _USB_VENDOR_BRANDS}


def _detect_usb_peripheral_ids() -> tuple[set[str], set[tuple[str, str]]]:
    """Return connected USB vendor IDs and vendor:device pairs for peripherals."""
    devices = detect_usb_devices()
    vendors: set[str] = set()
    ids: set[tuple[str, str]] = set()
    for d in devices:
        vendors.add(d.vendor_id)
        ids.add((d.vendor_id, d.device_id))
    return vendors, ids


def _match_peripheral_vendor(
    entry: PeripheralEntry,
    connected_vendors: set[str],
    connected_ids: set[tuple[str, str]] | None = None,
) -> bool:
    """Check if a peripheral entry matches a connected USB device.

    Checks in order:
    1. Specific USB vendor:device IDs from the entry's usb.ids file
    2. Vendor-only IDs from the entry's usb_vendors.ids file
    3. Fallback: brand keyword matching from _USB_VENDOR_BRANDS
    """
    if connected_ids and entry.usb_ids:
        for vid, did in entry.usb_ids:
            if (vid, did) in connected_ids:
                return True

    if entry.usb_vendor_ids:
        for vid in entry.usb_vendor_ids:
            if vid in connected_vendors:
                return True

    pkg = entry.package.lower()
    for vendor_id, keywords in _USB_VENDOR_BRANDS.items():
        if vendor_id in connected_vendors:
            if any(kw in pkg for kw in keywords):
                return True
    return False


# ---- Network printer discovery via mDNS/Avahi ----------------------------


@dataclass
class NetworkPrinter:
    """A printer discovered on the local network via mDNS."""

    name: str
    manufacturer: str
    model: str
    ip: str
    service_type: str


# Map mDNS manufacturer names → package-name keywords (lowercase).
_MDNS_MFG_KEYWORDS: dict[str, list[str]] = {
    "brother": ["brother"],
    "epson": ["epson"],
    "canon": ["canon", "cnijfilter", "scangearmp"],
    "hp": ["hp", "hplip"],
    "samsung": ["samsung"],
    "pantum": ["pantum"],
    "kyocera": ["kyocera"],
    "ricoh": ["ricoh"],
    "xerox": ["xerox"],
    "lexmark": ["lexmark"],
    "konica": ["konica"],
    "dell": ["dell"],
    "oki": ["oki"],
    "sharp": ["sharp"],
    "toshiba": ["toshiba"],
    "fuji": ["fuji"],
    "develop": ["develop"],
}


def detect_network_printers(timeout: int = 10) -> list[NetworkPrinter]:
    """Discover printers on the local network using avahi-browse (mDNS/DNS-SD).

    Scans for IPP, LPD, and PDL-datastream services. Extracts manufacturer
    and model info from the TXT records (usb_MFG, usb_MDL, ty fields).

    Returns a list of unique network printers found.
    """
    services = ["_ipp._tcp", "_printer._tcp", "_pdl-datastream._tcp"]
    printers: dict[str, NetworkPrinter] = {}  # keyed by ip to deduplicate

    for svc in services:
        output = _run(
            ["avahi-browse", "-t", "-r", "-p", svc],
            timeout=timeout,
        )
        if not output:
            continue

        for printer in _parse_avahi_output(output, svc):
            # Deduplicate by IP; prefer entries with more info
            existing = printers.get(printer.ip)
            if not existing or (not existing.model and printer.model):
                printers[printer.ip] = printer

    result = list(printers.values())
    _logger.info("Network printers discovered: %d", len(result))
    return result


def _decode_avahi_escapes(text: str) -> str:
    """Decode avahi-browse ``\\NNN`` decimal escape sequences."""
    return re.sub(r"\\(\d{3})", lambda m: chr(int(m.group(1))), text)


def _parse_avahi_output(output: str, service_type: str) -> list[NetworkPrinter]:
    """Parse avahi-browse -p output, extracting printer info from TXT records.

    avahi-browse -p format (parseable):
    =;iface;protocol;name;type;domain;hostname;address;port;txt

    TXT record fields of interest:
    - ty=<model name>
    - usb_MFG=<manufacturer>
    - usb_MDL=<model>
    - product=(<model>)
    """
    printers: list[NetworkPrinter] = []
    txt_re = re.compile(r'"([^"]*)"')

    for line in output.splitlines():
        if not line.startswith("="):
            continue

        parts = line.split(";")
        if len(parts) < 10:
            continue

        friendly_name = _decode_avahi_escapes(parts[3])
        address = parts[7]
        txt_field = parts[9] if len(parts) > 9 else ""

        # Parse TXT record key-value pairs
        txt_entries = txt_re.findall(txt_field)
        txt_dict: dict[str, str] = {}
        for entry in txt_entries:
            if "=" in entry:
                k, v = entry.split("=", 1)
                txt_dict[k.strip().lower()] = v.strip()

        manufacturer = txt_dict.get("usb_mfg", "")
        model = txt_dict.get("usb_mdl", "") or txt_dict.get("ty", "")
        if not model:
            # Try product field: product=(Model Name)
            product = txt_dict.get("product", "")
            if product.startswith("(") and product.endswith(")"):
                model = product[1:-1]

        if not manufacturer and friendly_name:
            # Guess manufacturer from the friendly name
            first_word = friendly_name.split()[0].lower() if friendly_name else ""
            for mfg_key in _MDNS_MFG_KEYWORDS:
                if first_word.startswith(mfg_key):
                    manufacturer = mfg_key.capitalize()
                    break

        printers.append(
            NetworkPrinter(
                name=friendly_name,
                manufacturer=manufacturer,
                model=model,
                ip=address,
                service_type=service_type,
            )
        )

    return printers


def match_network_printers(
    database: DriverDatabase,
    net_printers: list[NetworkPrinter],
) -> int:
    """Match network printers against the printer database.

    Updates ``detected`` and ``detected_device_name`` for printers that
    match a discovered network printer's manufacturer.

    Returns the number of newly detected printers.
    """
    if not net_printers:
        return 0

    # Build set of manufacturer keywords from discovered printers
    net_mfg_keywords: set[str] = set()
    for np in net_printers:
        mfg = np.manufacturer.lower()
        if mfg in _MDNS_MFG_KEYWORDS:
            net_mfg_keywords.update(_MDNS_MFG_KEYWORDS[mfg])
        elif mfg:
            net_mfg_keywords.add(mfg)

    newly_detected = 0
    for p in database.printers:
        if p.detected:
            continue
        pkg = p.package.lower()
        for kw in net_mfg_keywords:
            if kw in pkg:
                p.detected = True
                # Use the network printer name as the device name
                for np in net_printers:
                    if np.manufacturer.lower() in pkg or any(
                        k in pkg
                        for k in _MDNS_MFG_KEYWORDS.get(np.manufacturer.lower(), [])
                    ):
                        display = np.model or np.name
                        if np.ip:
                            display = f"{display} ({np.ip})"
                        p.detected_device_name = display
                        break
                newly_detected += 1
                break

    _logger.info("Network printer matches: %d new detections", newly_detected)
    return newly_detected
