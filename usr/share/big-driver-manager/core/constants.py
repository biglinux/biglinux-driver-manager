#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Constants and Configuration

This module centralizes all application constants, metadata,
and configuration values.
"""

import os

# Application Metadata
APP_NAME = "Big Driver Manager"
APP_ID = "br.com.biglinux.drivermanager"
APP_VERSION = "2.0.0"
APP_AUTHOR = "BigLinux Team"
APP_WEBSITE = "https://github.com/communitybig/big-driver-manager"

# Paths
CONFIG_DIR = os.path.expanduser("~/.config/big-driver-manager")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOG_DIR = os.path.expanduser("~/.local/share/big-driver-manager/logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

# Package Manager Settings
SUDO_COMMAND = "pkexec"
PACMAN_COMMAND = "pacman"

# UI Icon Sizes (pixels)
ICON_SIZE_HEADER = 40  # Section/card headers
ICON_SIZE_ITEM = 32  # Row items inside cards

# Kernel Patterns - True kernel packages (not modules)
KERNEL_PATTERNS = [
    r"^linux\d*$",  # Standard kernels (linux, linux59, etc.)
    r"^linux-lts$",  # Long term support kernel
    r"^linux\d*-lts$",  # LTS kernels with version number
    r"^linux-hardened$",  # Hardened kernel
    r"^linux-zen$",  # Zen kernel
    r"^linux-xanmod$",  # Xanmod kernel
    r"^linux\d*-xanmod$",  # Xanmod kernels with version number
    r"^linux-xanmod-lts$",  # Xanmod LTS kernel
    r"^linux\d*-xanmod-lts$",  # Xanmod LTS kernels with version number
    r"^linux\d*-rt$",  # Real-time kernels
    r"^linux-xanmod-x64v\d$",  # Xanmod optimized builds
    r"^linux-xanmod-lts-x64v\d$",  # Xanmod LTS optimized builds
    r"^linux-cachyos$",  # CachyOS kernel
    r"^linux-cachyos-lts$",  # CachyOS LTS kernel
]

# CachyOS kernels — detected when installed but NOT shown as installable
CACHYOS_PATTERNS = [
    r"^linux-cachyos$",
    r"^linux-cachyos-lts$",
]

# Excluded patterns (modules and other non-kernel packages)
EXCLUDED_PATTERNS = [
    r"-acpi_call",
    r"-bbswitch",
    r"-broadcom",
    r"-headers",
    r"-ndiswrapper",
    r"-nvidia",
    r"-r8168",
    r"-virtualbox",
    r"-zfs",
    r"-tp_smapi",
    r"-vhba-module",
    r"-rtl8723bu",
]

# LTS Kernel Feed URL
KERNEL_ORG_FEED_URL = "https://www.kernel.org/feeds/kdist.xml"

# Default LTS versions (fallback if fetch fails)
DEFAULT_LTS_VERSIONS = ["66", "612", "614"]

# Progress update intervals (seconds)
PROGRESS_UPDATE_INTERVAL = 0.5
STATUS_UPDATE_INTERVAL = 5.0

# UI Settings
WINDOW_DEFAULT_WIDTH = 1280
WINDOW_DEFAULT_HEIGHT = 720
WINDOW_MIN_WIDTH = 600
WINDOW_MIN_HEIGHT = 400
