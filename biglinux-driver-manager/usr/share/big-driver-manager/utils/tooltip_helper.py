"""
Tooltip helper — rich popover tooltips shown on hover for driver/firmware rows.

Adapted from big-video-converter's tooltip system. Uses Gtk.Popover with a
structured layout (icon + title + body) and a 200 ms hover delay so the tooltip
does not flash on quick mouse moves.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib

from utils.i18n import _


# ------------------------------------------------------------------
# Didactic tips per category — shown in every tooltip of that type
# ------------------------------------------------------------------


def _category_tips() -> dict[str, str]:
    """Return translated didactic tip per category id."""
    return {
        "wifi": _(
            "If your Wi-Fi is already working, the built-in kernel driver "
            "is usually the best option. Install an alternative only if "
            "you have connection problems."
        ),
        "ethernet": _(
            "Wired network adapters almost always work out of the box. "
            "An extra driver is only needed for very new or rare hardware."
        ),
        "bluetooth": _(
            "Some Bluetooth adapters need extra firmware to work. "
            "If pairing fails, installing the firmware for your adapter "
            "may solve the problem."
        ),
        "dvb": _(
            "Digital TV tuners usually need specific firmware. "
            "Without it the device won't be recognized by the system."
        ),
        "sound": _(
            "Most audio devices work with ALSA built into the kernel. "
            "Extra firmware is only needed for specific USB audio interfaces."
        ),
        "webcam": _(
            "Most webcams work automatically. Extra firmware may improve "
            "image quality or enable additional features."
        ),
        "touchscreen": _(
            "If your touchscreen doesn't respond, installing the matching "
            "firmware usually fixes it."
        ),
        "printer": _(
            "Printer drivers let the system communicate with your model. "
            "If the printer was detected on your network or USB, installing "
            "the matching driver is recommended."
        ),
        "printer3d": _(
            "3D printer firmware enables communication between the slicer "
            "and the printer hardware."
        ),
        "scanner": _(
            "Scanner drivers (SANE backends) allow scanning applications to "
            "communicate with your scanner model."
        ),
        "other": _("Additional firmware packages for specialized hardware."),
    }


def build_tooltip_body(
    item,
    category_id: str,
) -> str:
    """Build a structured tooltip body string for a driver/firmware/peripheral.

    Parameters
    ----------
    item:
        A DriverModule, FirmwareEntry, or PeripheralEntry.
    category_id:
        The sidebar category key (wifi, printer, etc.).

    Returns
    -------
    str
        Multi-line plain text suitable for a tooltip label.
    """
    from utils.desc_translate import translate_description

    lines: list[str] = []

    # Package name
    lines.append(f"{_('Package')}: {item.name}")

    # Status
    detected = getattr(item, "detected", False)
    installed = getattr(item, "installed", False)
    if detected and installed:
        lines.append(f"{_('Status')}: {_('Detected and installed')} ✓")
    elif detected:
        lines.append(f"{_('Status')}: {_('Detected — not yet installed')}")
    elif installed:
        lines.append(f"{_('Status')}: {_('Installed')} ✓")
    else:
        lines.append(f"{_('Status')}: {_('Available in repository')}")

    # Device name (if detected)
    device_name = getattr(item, "detected_device_name", None)
    if device_name:
        lines.append(f"{_('Device')}: {device_name}")

    # Description
    desc = getattr(item, "description", "")
    if desc and desc.strip():
        translated = translate_description(desc.strip())
        lines.append(f"\n{translated}")

    # Didactic tip
    tips = _category_tips()
    tip = tips.get(category_id, "")
    if tip:
        lines.append(f"\n💡 {tip}")

    return "\n".join(lines)


class TooltipHelper:
    """Manages rich popover tooltips across the application."""

    def __init__(self) -> None:
        self._popovers: dict[int, Gtk.Popover] = {}
        self._timers: dict[int, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_tooltip(
        self,
        widget: Gtk.Widget,
        title: str,
        body: str,
        icon_name: str = "dialog-information-symbolic",
    ) -> None:
        """Attach a rich popover tooltip to *widget*.

        Parameters
        ----------
        widget:
            Target widget (usually a row Box).
        title:
            Bold heading shown in the popover.
        body:
            Multi-line descriptive text.
        icon_name:
            Symbolic icon displayed beside the title.
        """
        popover = self._build_popover(widget, title, body, icon_name)
        wid = id(widget)
        self._popovers[wid] = popover

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", self._on_enter, wid, popover)
        motion.connect("leave", self._on_leave, wid, popover)
        widget.add_controller(motion)

    def cleanup(self) -> None:
        """Remove all popovers and cancel pending timers."""
        for timer_id in self._timers.values():
            GLib.source_remove(timer_id)
        self._timers.clear()
        for popover in self._popovers.values():
            popover.unparent()
        self._popovers.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_popover(
        parent: Gtk.Widget,
        title: str,
        body: str,
        icon_name: str,
    ) -> Gtk.Popover:
        popover = Gtk.Popover()
        popover.set_autohide(False)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.set_parent(parent)
        popover.add_css_class("tooltip-popover")

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        outer.set_margin_start(14)
        outer.set_margin_end(14)
        outer.set_margin_top(10)
        outer.set_margin_bottom(10)

        # Header row: icon + title
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(18)
        icon.add_css_class("accent")
        hdr.append(icon)

        title_lbl = Gtk.Label(label=title)
        title_lbl.set_xalign(0)
        title_lbl.add_css_class("heading")
        title_lbl.set_hexpand(True)
        hdr.append(title_lbl)
        outer.append(hdr)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(2)
        sep.set_margin_bottom(2)
        outer.append(sep)

        # Body text
        body_lbl = Gtk.Label(label=body)
        body_lbl.set_xalign(0)
        body_lbl.set_wrap(True)
        body_lbl.set_max_width_chars(52)
        body_lbl.add_css_class("caption")
        outer.append(body_lbl)

        popover.set_child(outer)
        return popover

    # -- Hover handlers ------------------------------------------------

    def _on_enter(
        self,
        _ctrl: Gtk.EventControllerMotion,
        _x: float,
        _y: float,
        wid: int,
        popover: Gtk.Popover,
    ) -> None:
        if wid in self._timers:
            GLib.source_remove(self._timers[wid])
        self._timers[wid] = GLib.timeout_add(200, self._show_popover, wid, popover)

    def _on_leave(
        self,
        _ctrl: Gtk.EventControllerMotion,
        wid: int,
        popover: Gtk.Popover,
    ) -> None:
        if wid in self._timers:
            GLib.source_remove(self._timers[wid])
            del self._timers[wid]
        popover.popdown()

    def _show_popover(self, wid: int, popover: Gtk.Popover) -> bool:
        self._timers.pop(wid, None)
        popover.popup()
        return False  # one-shot
