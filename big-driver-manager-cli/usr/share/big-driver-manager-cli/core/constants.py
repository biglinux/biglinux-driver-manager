#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Big Driver Manager - Constants and Configuration

This module centralizes all application constants, metadata,
and configuration values.
"""

import os
import re

# Application Metadata
APP_NAME = "Big Driver Manager"
APP_ID = "br.com.biglinux.drivermanager"
APP_VERSION = "2.0.1"
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
    r"^linux-big\d+$",  # BigCommunity kernels, one per series, see is_big_kernel
]

# BigCommunity kernels (big-kernel project). One package per series, as
# Manjaro's linuxNN: linux-big72, linux-big73, with modules named
# "linux-big73-<module>" and ``uname -r`` ending in "-big" (7.3.1-1-big).
# BIG_KERNEL, "linux-big", is a metapackage that depends on the current
# series; before the series were split it was the 7.2 kernel itself, and a
# machine not yet updated may still have it as one.
BIG_KERNEL = "linux-big"
BIG_KERNEL_RE = r"linux-big\d+"
BIG_KERNEL_RELEASE_SUFFIX = "-big"


def is_big_kernel(name: str) -> bool:
    """A BigCommunity kernel package: linux-big73, or the pre-split linux-big."""
    return name == BIG_KERNEL or re.fullmatch(BIG_KERNEL_RE, name) is not None


# Kernel module packages a machine can't boot/work without when the running
# kernel uses them (display, Wi-Fi, power). A kernel whose repo lacks the
# matching module must not be offered — it would boot without the driver.
REQUIRED_MODULE_SUFFIX_RE = r"-(nvidia(-\d+xx)?(-open)?|broadcom-wl|bbswitch)$"

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

# Default LTS kernel versions (fallback when kernel.org feed is unreachable
# and no previous feed result is cached — see KernelManager.lts_versions).
# Encoded as "majorminor" (e.g. "612" = Linux 6.12) to match the package naming
# scheme used by Manjaro/BigLinux (linux612, linux66, etc.). Keep this list in
# sync with https://www.kernel.org/category/releases.html.
DEFAULT_LTS_VERSIONS = ["61", "66", "510", "515", "612", "618"]

# Progress update intervals (seconds)
PROGRESS_UPDATE_INTERVAL = 0.5
STATUS_UPDATE_INTERVAL = 5.0
