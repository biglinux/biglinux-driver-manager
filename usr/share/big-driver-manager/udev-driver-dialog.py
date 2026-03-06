#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Standalone GTK4/Adw dialog for driver availability notifications.

Launched by udev-notify.sh (hotplug) or login-check-drivers.sh (timer).
Shows available driver info and lets the user install or ignore.

Usage:
    python3 udev-driver-dialog.py BUS VID DID CATEGORY DRIVER_NAME PACKAGE DESCRIPTION

BUS is one of: usb, pci, firmware
VID:DID is the device ID pair (or 0000:0000 for firmware)
CATEGORY is: device-ids, firmware, printer, scanner
DRIVER_NAME is the human-readable driver folder name
PACKAGE is the pacman package to install
DESCRIPTION is a brief explanation of the driver
"""

import gettext
import json
import os
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

_APP_ID = "br.com.biglinux.drivermanager.udev"
_DOMAIN = "big-driver-manager"

# --- i18n ---
_locale_dir = "/usr/share/locale"
_script_dir = os.path.dirname(os.path.abspath(__file__))
_share_locale = os.path.join(os.path.dirname(os.path.dirname(_script_dir)), "locale")
if os.path.isdir(_share_locale):
    _locale_dir = _share_locale

gettext.bindtextdomain(_DOMAIN, _locale_dir)
gettext.textdomain(_DOMAIN)
_ = gettext.gettext


# --- Blacklist helpers ---
def _blacklist_path() -> str:
    config_dir = os.environ.get(
        "XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config")
    )
    return os.path.join(config_dir, "big-driver-manager", "ignored_devices.json")


def _load_blacklist() -> list[str]:
    path = _blacklist_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_blacklist(entries: list[str]) -> None:
    path = _blacklist_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sorted(set(entries)), fh, indent=2)


# --- Parse CLI args ---
def _parse_args() -> tuple[str, str, str, str, str, str, str] | None:
    if len(sys.argv) < 8:
        return None
    return (
        sys.argv[1],  # bus
        sys.argv[2],  # vid
        sys.argv[3],  # did
        sys.argv[4],  # category
        sys.argv[5],  # driver_name
        sys.argv[6],  # package
        sys.argv[7],  # description
    )


# --- Build title by category ---
def _title_for_category(category: str) -> str:
    titles = {
        "firmware": _("Firmware available"),
        "printer": _("Printer driver available"),
        "scanner": _("Scanner driver available"),
    }
    return titles.get(category, _("Driver available"))


class DriverDialog(Adw.Application):
    """Single-window Adw app showing a driver notification dialog."""

    def __init__(
        self,
        bus: str,
        vid: str,
        did: str,
        category: str,
        driver_name: str,
        package: str,
        description: str,
    ) -> None:
        super().__init__(application_id=_APP_ID, flags=Gio.ApplicationFlags.NON_UNIQUE)
        self._bus = bus
        self._vid = vid
        self._did = did
        self._category = category
        self._driver_name = driver_name
        self._package = package
        self._description = description

    def do_activate(self) -> None:
        win = Adw.ApplicationWindow(
            application=self, default_width=440, default_height=-1
        )
        win.set_resizable(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_bottom(24)
        box.set_margin_start(24)
        box.set_margin_end(24)

        # Title
        title = _title_for_category(self._category)
        title_label = Gtk.Label(label=title)
        title_label.add_css_class("title-1")
        box.append(title_label)

        # Driver name
        name_label = Gtk.Label(label=self._driver_name)
        name_label.add_css_class("title-3")
        name_label.set_wrap(True)
        box.append(name_label)

        # Description
        if self._description:
            desc_label = Gtk.Label(label=self._description)
            desc_label.set_wrap(True)
            desc_label.set_xalign(0)
            desc_label.add_css_class("dim-label")
            box.append(desc_label)

        # Package info
        pkg_label = Gtk.Label(label=f"📦 {self._package}")
        pkg_label.set_xalign(0)
        box.append(pkg_label)

        # Ignore switch
        ignore_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ignore_row.set_margin_top(8)
        self._ignore_switch = Gtk.Switch()
        self._ignore_switch.set_valign(Gtk.Align.CENTER)

        if self._category == "firmware":
            ignore_label_text = _("Don't alert for this device again")
        else:
            ignore_label_text = _("Don't alert for this device again")
        ignore_label = Gtk.Label(label=ignore_label_text)
        ignore_label.set_hexpand(True)
        ignore_label.set_xalign(0)

        ignore_row.append(ignore_label)
        ignore_row.append(self._ignore_switch)
        box.append(ignore_row)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_margin_top(12)
        btn_box.set_halign(Gtk.Align.END)

        cancel_btn = Gtk.Button(label=_("Cancel"))
        cancel_btn.connect("clicked", self._on_cancel)
        btn_box.append(cancel_btn)

        install_btn = Gtk.Button(label=_("Install"))
        install_btn.add_css_class("suggested-action")
        install_btn.connect("clicked", self._on_install)
        btn_box.append(install_btn)

        box.append(btn_box)
        win.set_content(box)
        win.present()

    def _blacklist_key(self) -> str:
        if self._category == "firmware":
            return f"fw:{self._package}"
        return f"{self._vid}:{self._did}"

    def _maybe_blacklist(self) -> None:
        if self._ignore_switch.get_active():
            bl = _load_blacklist()
            bl.append(self._blacklist_key())
            _save_blacklist(bl)

    def _on_cancel(self, _btn: Gtk.Button) -> None:
        self._maybe_blacklist()
        self.quit()

    def _on_install(self, _btn: Gtk.Button) -> None:
        self._maybe_blacklist()
        # Launch big-driver-manager in the user session scope so it survives
        # after this transient dialog process exits.
        try:
            subprocess.Popen(
                [
                    "systemd-run",
                    "--user",
                    "--scope",
                    "--",
                    "big-driver-manager",
                ],
                start_new_session=True,
            )
        except OSError:
            pass
        # Give a moment for the process to spawn, then quit
        GLib.timeout_add(500, self.quit)


def main() -> None:
    args = _parse_args()
    if args is None:
        print(
            f"Usage: {sys.argv[0]} BUS VID DID CATEGORY DRIVER_NAME PACKAGE DESCRIPTION",
            file=sys.stderr,
        )
        sys.exit(1)

    bus, vid, did, category, driver_name, package, description = args
    app = DriverDialog(bus, vid, did, category, driver_name, package, description)
    app.run([])


if __name__ == "__main__":
    main()
