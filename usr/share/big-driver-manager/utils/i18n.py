#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Internationalization support for Big Driver Manager."""

import gettext
import os

# Determine locale directory
# Priority: 1) Local project locale, 2) AppImage, 3) System install
locale_dir = "/usr/share/locale"  # Default fallback for system install

# Check if running from source/local (e.g. python main.py from the project)
script_dir = os.path.dirname(os.path.abspath(__file__))  # utils/
app_dir = os.path.dirname(script_dir)  # big-driver-manager/
share_dir = os.path.dirname(app_dir)  # share/
local_locale = os.path.join(share_dir, "locale")  # share/locale

if os.path.isdir(local_locale):
    locale_dir = local_locale

# Check if we're in an AppImage (overrides local)
if "APPIMAGE" in os.environ or "APPDIR" in os.environ:
    appimage_locale = os.path.join(share_dir, "locale")
    if os.path.isdir(appimage_locale):
        locale_dir = appimage_locale

# Configure the translation text domain for big-driver-manager
gettext.bindtextdomain("big-driver-manager", locale_dir)
gettext.textdomain("big-driver-manager")

# Export _ directly as the translation function
_ = gettext.gettext
