"""Shared GTK4 helpers used across UI modules."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def clear_box(box: Gtk.Box) -> None:
    """Remove every child widget from a :class:`Gtk.Box`."""
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def clear_listbox(listbox: Gtk.ListBox) -> None:
    """Remove every row from a :class:`Gtk.ListBox`."""
    row = listbox.get_first_child()
    while row is not None:
        nxt = row.get_next_sibling()
        listbox.remove(row)
        row = nxt


def clear_flow(flow: Gtk.FlowBox) -> None:
    """Remove every child from a :class:`Gtk.FlowBox`."""
    child = flow.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        flow.remove(child)
        child = nxt
