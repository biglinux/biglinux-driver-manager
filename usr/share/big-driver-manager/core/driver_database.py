#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Driver Database — loads device-ids, firmware, printer, and scanner databases.

Reads the flat-file database structure from assets/ and provides
typed data objects for the UI and detection layers.
"""

from dataclasses import dataclass, field
from pathlib import Path

from core.logging_config import get_logger

_logger = get_logger("DriverDatabase")

# Base path for all asset databases
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@dataclass
class DriverModule:
    """A hardware driver module with device-id matching."""

    name: str
    category: str
    description: str
    package: str
    pci_ids: list[tuple[str, str]] = field(default_factory=list)
    usb_ids: list[tuple[str, str]] = field(default_factory=list)
    sdio_ids: list[tuple[str, str]] = field(default_factory=list)
    detected: bool = False
    installed: bool = False
    detected_device_name: str | None = None
    device_has_driver: bool = False
    # Kernel driver currently bound to the matched device (e.g. "r8152")
    device_driver: str = ""
    # None = unknown (not checked yet), False = AUR / not in enabled repos
    in_repo: bool | None = None


@dataclass
class FirmwareEntry:
    """A firmware package entry."""

    name: str
    category: str
    description: str
    package: str
    firmware_files: list[str] = field(default_factory=list)
    detected: bool = False
    installed: bool = False
    in_repo: bool | None = None


@dataclass
class PeripheralEntry:
    """A printer or scanner package entry."""

    name: str
    description: str
    package: str
    usb_vendor_ids: list[str] = field(default_factory=list)
    usb_ids: list[tuple[str, str]] = field(default_factory=list)
    installed: bool = False
    detected: bool = False
    detected_device_name: str | None = None
    in_repo: bool | None = None


def _parse_ids_file(path: Path) -> list[tuple[str, str]]:
    """Parse a .ids file with VENDOR:DEVICE pairs, one per line or comma-separated."""
    if not path.exists():
        return []
    ids: list[tuple[str, str]] = []
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    for token in text.replace("\n", ",").split(","):
        token = token.strip()
        if ":" in token:
            parts = token.split(":", 1)
            vendor = parts[0].strip().upper()
            device = parts[1].strip().upper()
            if vendor and device:
                ids.append((vendor, device))
    return ids


def _parse_vendor_ids_file(path: Path) -> list[str]:
    """Parse a vendor IDs file with one vendor ID per line (hex, e.g. 04F9)."""
    if not path.exists():
        return []
    vendors: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        token = line.split("#", 1)[0].strip().upper()
        if token:
            vendors.append(token)
    return vendors


# Categories shown by the UI; anything else is logged and falls into "other".
# Old/alternative spellings found in the asset files are mapped here.
MODULE_CATEGORIES = frozenset({"wifi", "ethernet", "bluetooth", "other"})
_CATEGORY_ALIASES = {"wireless": "wifi", "wired": "ethernet"}


def normalize_category(raw: str) -> str:
    """Normalize a module category read from disk (case, aliases)."""
    cat = raw.strip().lower()
    cat = _CATEGORY_ALIASES.get(cat, cat)
    return cat if cat in MODULE_CATEGORIES else "other"


def _read_text(path: Path) -> str:
    """Read a single-line text file, stripped."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


class DriverDatabase:
    """Loads and holds all driver/firmware/peripheral databases."""

    def __init__(self, assets_dir: Path | None = None) -> None:
        self._base = assets_dir or _ASSETS_DIR
        self.modules: list[DriverModule] = []
        self.firmware: list[FirmwareEntry] = []
        self.printers: list[PeripheralEntry] = []
        self.scanners: list[PeripheralEntry] = []
        self._load_all()

    def _load_all(self) -> None:
        self._load_device_ids()
        self._load_firmware()
        self._load_peripherals("printer", self.printers)
        self._load_peripherals("scanner", self.scanners)
        _logger.info(
            "Database loaded: %d modules, %d firmware, %d printers, %d scanners",
            len(self.modules),
            len(self.firmware),
            len(self.printers),
            len(self.scanners),
        )

    def _load_device_ids(self) -> None:
        base = self._base / "device-ids"
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            raw_category = _read_text(entry / "category") or "other"
            category = normalize_category(raw_category)
            if category != raw_category:
                _logger.warning(
                    "device-ids/%s: category %r normalized to %r",
                    name,
                    raw_category,
                    category,
                )
            description = _read_text(entry / "description")
            package = _read_text(entry / "pkg") or name
            pci_ids = _parse_ids_file(entry / "pci.ids")
            usb_ids = _parse_ids_file(entry / "usb.ids")
            sdio_ids = _parse_ids_file(entry / "sdio.ids")
            self.modules.append(
                DriverModule(
                    name=name,
                    category=category,
                    description=description,
                    package=package,
                    pci_ids=pci_ids,
                    usb_ids=usb_ids,
                    sdio_ids=sdio_ids,
                )
            )

    def _load_firmware(self) -> None:
        base = self._base / "firmware"
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            category = _read_text(entry / "category") or "firmware"
            description = _read_text(entry / "description")
            # Firmware files listed in a file named after the package
            fw_file = entry / name
            firmware_files: list[str] = []
            if fw_file.is_file():
                firmware_files = [
                    line.strip()
                    for line in fw_file.read_text(
                        encoding="utf-8", errors="replace"
                    ).splitlines()
                    if line.strip()
                ]
            self.firmware.append(
                FirmwareEntry(
                    name=name,
                    category=category,
                    description=description,
                    package=name,
                    firmware_files=firmware_files,
                )
            )

    def _load_peripherals(self, kind: str, target: list[PeripheralEntry]) -> None:
        base = self._base / kind
        if not base.is_dir():
            return
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            description = _read_text(entry / "description")
            usb_vendor_ids = _parse_vendor_ids_file(entry / "usb_vendors.ids")
            usb_ids = _parse_ids_file(entry / "usb.ids")
            target.append(
                PeripheralEntry(
                    name=name,
                    description=description,
                    package=name,
                    usb_vendor_ids=usb_vendor_ids,
                    usb_ids=usb_ids,
                )
            )

    def get_modules_by_category(self, category: str) -> list[DriverModule]:
        return [m for m in self.modules if m.category == category]

    def get_firmware_by_category(self, category: str) -> list[FirmwareEntry]:
        """Return firmware entries whose category contains the given keyword."""
        return [fw for fw in self.firmware if category in fw.category.split()]

    def all_entries(self) -> list[DriverModule | FirmwareEntry | PeripheralEntry]:
        """Return every module, firmware and peripheral entry."""
        return [*self.modules, *self.firmware, *self.printers, *self.scanners]

    def get_all_categories(self) -> list[str]:
        cats = sorted({m.category for m in self.modules})
        return cats

    def get_all_firmware_categories(self) -> set[str]:
        """Return all unique firmware subcategories."""
        cats: set[str] = set()
        for fw in self.firmware:
            for c in fw.category.split():
                cats.add(c)
        return cats
