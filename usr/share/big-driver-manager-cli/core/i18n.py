"""Translations for messages produced by the core.

The core shares the text domain of the graphical interface
(biglinux-driver-manager), whose package installs the catalogs. Without it
installed -- the live session, the installer -- messages stay in English.
"""

import gettext
import os

DOMAIN = "biglinux-driver-manager"
LOCALE_DIR = os.environ.get("BDM_LOCALE_DIR", "/usr/share/locale")

_ = gettext.translation(DOMAIN, LOCALE_DIR, fallback=True).gettext
