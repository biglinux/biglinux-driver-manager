"""Translations for messages produced by the core.

The command line's own messages live in its text domain
(big-driver-manager-cli), shipped with this package. Messages the core shares
with the graphical interface fall back to the interface's domain
(biglinux-driver-manager), whose package installs those catalogs. Without
either catalog -- or in a language neither has -- messages stay in English.
"""

import gettext
import os

DOMAIN = "biglinux-driver-manager"
CLI_DOMAIN = "big-driver-manager-cli"
LOCALE_DIR = "/usr/share/locale"
if os.geteuid() != 0:  # an override is for development, never for root
    LOCALE_DIR = os.environ.get("BDM_LOCALE_DIR", LOCALE_DIR)

_translation = gettext.translation(CLI_DOMAIN, LOCALE_DIR, fallback=True)
_translation.add_fallback(gettext.translation(DOMAIN, LOCALE_DIR, fallback=True))
_ = _translation.gettext
ngettext = _translation.ngettext


def use_for_argparse() -> None:
    """argparse translates "usage:", "options" and its errors through the
    global domain: point it at the command line's catalog."""
    gettext.bindtextdomain(CLI_DOMAIN, LOCALE_DIR)
    gettext.textdomain(CLI_DOMAIN)
