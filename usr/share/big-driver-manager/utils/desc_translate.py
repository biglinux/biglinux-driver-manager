"""Translate driver/firmware/peripheral descriptions at display time.

Strategy: replace well-known English phrases with gettext-translated
equivalents while preserving brand names and model identifiers intact.

Phrases are matched case-insensitively and replaced longest-first so that
"color multifunction printer" matches before "multifunction printer".
"""

import re

from utils.i18n import _

# -- Translatable phrase pairs ------------------------------------------------
# Each tuple is (english_phrase, translatable_phrase).
# The translatable_phrase is wrapped in _() at lookup time so gettext can
# find the string in the .pot catalog.
#
# ORDER DOES NOT MATTER here — the code sorts by length (longest first)
# before applying replacements.

_PHRASE_MAP: list[tuple[str, str]] = [
    # --- Printer descriptions (most common) ---
    ("printing driver for", "Printing driver for"),
    ("printer driver for", "Printer driver for"),
    ("driver for the", "Driver for the"),
    ("driver for", "Driver for"),
    (
        "driver set (printing and scanning) for",
        "Driver set (printing and scanning) for",
    ),
    (
        "complete stand alone driver set (printing and scanning) for",
        "Complete stand-alone driver set (printing and scanning) for",
    ),
    ("lpr and cups driver for the", "LPR and CUPS driver for the"),
    ("lpr and cups driver for", "LPR and CUPS driver for"),
    ("lpr driver and cups wrapper for", "LPR driver and CUPS wrapper for"),
    ("lpr driver for", "LPR driver for"),
    ("cups wrapper for", "CUPS wrapper for"),
    ("cups driver for the", "CUPS driver for the"),
    ("cups driver for", "CUPS driver for"),
    ("cups and lpr drivers for the", "CUPS and LPR drivers for the"),
    ("cups printer driver", "CUPS printer driver"),
    ("cups driver", "CUPS driver"),
    ("color multifunction printer", "color multifunction printer"),
    ("multifunction printer", "multifunction printer"),
    ("ink tank multifunction printer", "ink tank multifunction printer"),
    ("multifuncional printer", "multifunction printer"),
    ("wifi multifuncional printer", "Wi-Fi multifunction printer"),
    ("color laser printer", "color laser printer"),
    ("laser printer driver", "laser printer driver"),
    ("laser printer", "laser printer"),
    ("inkjet printer driver", "inkjet printer driver"),
    ("inkjet printer", "inkjet printer"),
    ("inkjet printers", "inkjet printers"),
    ("label and receipt printer", "label and receipt printer"),
    ("label printer", "label printer"),
    ("laser printers", "laser printers"),
    ("printer communication", "printer communication"),
    ("print system integration", "print system integration"),
    ("series inkjet printer", "series inkjet printer"),
    ("multifunction inkjet", "multifunction inkjet"),
    ("(printer communication)", "(printer communication)"),
    ("(print system integration)", "(print system integration)"),
    # --- device-ids descriptions ---
    ("wi-fi driver for", "Wi-Fi driver for"),
    ("wifi driver for", "Wi-Fi driver for"),
    ("dkms driver for", "DKMS driver for"),
    ("wired network driver for", "Wired network driver for"),
    ("bluetooth driver for", "Bluetooth driver for"),
    ("kernel driver module for", "Kernel driver module for"),
    ("wireless driver", "wireless driver"),
    ("wireless adapters", "wireless adapters"),
    ("usb wireless adapters", "USB wireless adapters"),
    ("usb dual-band wireless adapters", "USB dual-band wireless adapters"),
    ("usb tri-band wireless adapters", "USB tri-band wireless adapters"),
    ("ethernet driver", "Ethernet driver"),
    (
        "monitor mode & frame injection support",
        "monitor mode & frame injection support",
    ),
    # --- Firmware descriptions ---
    ("firmware for", "Firmware for"),
    ("bluetooth firmware for", "Bluetooth firmware for"),
    ("firmware files for", "Firmware files for"),
    ("digital tv (dvb) receivers", "digital TV (DVB) receivers"),
    ("digital tv (dvb) tuners", "digital TV (DVB) tuners"),
    ("digital tv tuner", "digital TV tuner"),
    ("wireless networking chips", "wireless networking chips"),
    ("wi-fi chips", "Wi-Fi chips"),
    ("wireless cards", "wireless cards"),
    ("wireless adapters", "wireless adapters"),
    ("network adapters", "network adapters"),
    ("touchscreen controllers", "touchscreen controllers"),
    ("usb audio interfaces", "USB audio interfaces"),
    ("usb logic analyzers", "USB logic analyzers"),
    ("usb midi interfaces", "USB MIDI interfaces"),
    ("controller cards", "controller cards"),
    ("controller chips", "controller chips"),
    ("scsi controllers", "SCSI controllers"),
    ("legacy devices only", "legacy devices only"),
    ("stable tested version", "stable tested version"),
    ("latest release", "latest release"),
    # --- Scanner descriptions ---
    ("scanner software for", "Scanner software for"),
    ("scanner driver for", "Scanner driver for"),
    ("sane scanner driver for", "SANE scanner driver for"),
    ("scanner plugin for image scan!", "scanner plugin for Image Scan!"),
    ("image scan! plugin for", "Image Scan! plugin for"),
    ("image scan! frontend for", "Image Scan! frontend for"),
    ("data files required by", "Data files required by"),
    ("scanners and multifunction printers", "scanners and multifunction printers"),
    ("multifunction printers", "multifunction printers"),
    ("flatbed and all-in-one scanners", "flatbed and all-in-one scanners"),
    ("usb and network scanners", "USB and network scanners"),
    ("network and usb scanners", "network and USB scanners"),
    ("portable document scanner", "portable document scanner"),
    ("one-touch scanning", "one-touch scanning"),
    ("scanner panel button", "scanner panel button"),
    # --- Common suffixes/qualifiers ---
    ("printers, supplied by", "printers, supplied by"),
    ("ppd files for", "PPD files for"),
    ("administration tool for managing", "Administration tool for managing"),
    ("printers on your network", "printers on your network"),
    ("(proprietary)", "(proprietary)"),
]


def _build_replacements() -> list[tuple[re.Pattern[str], str]]:
    """Pre-compile phrase patterns, sorted longest-first."""
    # Deduplicate and sort by length descending
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for eng, trans in _PHRASE_MAP:
        key = eng.lower()
        if key not in seen:
            seen.add(key)
            pairs.append((eng, trans))

    pairs.sort(key=lambda p: -len(p[0]))

    compiled: list[tuple[re.Pattern[str], str]] = []
    for eng, trans in pairs:
        pattern = re.compile(re.escape(eng), re.IGNORECASE)
        compiled.append((pattern, trans))
    return compiled


_REPLACEMENTS = _build_replacements()


def translate_description(desc: str) -> str:
    """Translate an English driver description preserving model names.

    Applies phrase-level translation via gettext. Brand names and model
    identifiers (e.g. RTL8812AU, DCP-J525W) are left untouched.
    """
    if not desc:
        return desc

    result = desc
    for pattern, translatable in _REPLACEMENTS:
        result = pattern.sub(lambda m, t=translatable: _(t), result, count=1)

    return result


# -- xgettext extraction block ------------------------------------------------
# The strings below are never executed at runtime. They exist solely so that
# xgettext can discover the translatable phrases when scanning this file.
def _xgettext_strings() -> None:  # pragma: no cover
    _("Printing driver for")
    _("Printer driver for")
    _("Driver for the")
    _("Driver for")
    _("Driver set (printing and scanning) for")
    _("Complete stand-alone driver set (printing and scanning) for")
    _("LPR and CUPS driver for the")
    _("LPR and CUPS driver for")
    _("LPR driver and CUPS wrapper for")
    _("LPR driver for")
    _("CUPS wrapper for")
    _("CUPS driver for the")
    _("CUPS driver for")
    _("CUPS and LPR drivers for the")
    _("CUPS printer driver")
    _("CUPS driver")
    _("color multifunction printer")
    _("multifunction printer")
    _("ink tank multifunction printer")
    _("Wi-Fi multifunction printer")
    _("color laser printer")
    _("laser printer driver")
    _("laser printer")
    _("inkjet printer driver")
    _("inkjet printer")
    _("inkjet printers")
    _("label and receipt printer")
    _("label printer")
    _("laser printers")
    _("printer communication")
    _("print system integration")
    _("series inkjet printer")
    _("multifunction inkjet")
    _("(printer communication)")
    _("(print system integration)")
    _("Wi-Fi driver for")
    _("DKMS driver for")
    _("Wired network driver for")
    _("Bluetooth driver for")
    _("Kernel driver module for")
    _("wireless driver")
    _("wireless adapters")
    _("USB wireless adapters")
    _("USB dual-band wireless adapters")
    _("USB tri-band wireless adapters")
    _("Ethernet driver")
    _("monitor mode & frame injection support")
    _("Firmware for")
    _("Bluetooth firmware for")
    _("Firmware files for")
    _("digital TV (DVB) receivers")
    _("digital TV (DVB) tuners")
    _("digital TV tuner")
    _("wireless networking chips")
    _("Wi-Fi chips")
    _("wireless cards")
    _("network adapters")
    _("touchscreen controllers")
    _("USB audio interfaces")
    _("USB logic analyzers")
    _("USB MIDI interfaces")
    _("controller cards")
    _("controller chips")
    _("SCSI controllers")
    _("legacy devices only")
    _("stable tested version")
    _("latest release")
    _("Scanner software for")
    _("Scanner driver for")
    _("SANE scanner driver for")
    _("scanner plugin for Image Scan!")
    _("Image Scan! plugin for")
    _("Image Scan! frontend for")
    _("Data files required by")
    _("scanners and multifunction printers")
    _("multifunction printers")
    _("flatbed and all-in-one scanners")
    _("USB and network scanners")
    _("network and USB scanners")
    _("portable document scanner")
    _("one-touch scanning")
    _("scanner panel button")
    _("printers, supplied by")
    _("PPD files for")
    _("Administration tool for managing")
    _("printers on your network")
    _("(proprietary)")
