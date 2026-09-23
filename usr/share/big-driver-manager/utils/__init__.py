"""Utils package for Big Driver Manager application."""

from utils.i18n import _

__all__ = [
    "_",
]

# NOTE: ``utils.gtk_helpers`` intentionally isn't re-exported here —
# importing it would pull in gi/Gtk at interpreter start even for non-UI
# tools (e.g. translation scripts). Import the submodule directly:
# ``from utils.gtk_helpers import clear_box``.
