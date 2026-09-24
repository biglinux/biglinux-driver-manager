"""Kernel card visual helpers — pure functions shared by KernelSection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from utils.i18n import _


# ------------------------------------------------------------------
# Kernel type classification
# ------------------------------------------------------------------


@dataclass(frozen=True)
class KernelTypeInfo:
    """Resolved type metadata for a kernel."""

    is_lts: bool = False
    is_rt: bool = False
    is_xanmod: bool = False
    is_cachyos: bool = False
    is_big: bool = False
    type_desc: str = ""
    full_desc: str = ""
    badge_entries: list[tuple[str, str]] = field(default_factory=list)


def classify_kernel(kernel: dict) -> KernelTypeInfo:
    """Derive type flags, descriptions and badge entries from a kernel dict."""
    name = kernel.get("name", "")
    is_lts = kernel.get("lts", False) or "-lts" in name
    is_rt = kernel.get("rt", False) or "-rt" in name
    is_xanmod = kernel.get("xanmod", False) or "xanmod" in name
    is_cachyos = kernel.get("cachyos", False) or "cachyos" in name
    is_big = kernel.get("big", False) or name == "linux-big"

    type_parts: list[str] = []
    full_parts: list[str] = []
    badges: list[tuple[str, str]] = []

    if is_lts:
        type_parts.append(_("Stable, long-term support"))
        full_parts.append(
            _(
                "Receives security updates for years. "
                "Best choice for most users — reliable and well-tested."
            )
        )
        badges.append(("LTS", "success"))
    if is_rt:
        type_parts.append(_("Low-latency, real-time"))
        full_parts.append(
            _(
                "Designed for audio/video production and tasks needing precise timing. "
                "May be incompatible with some drivers (e.g. NVIDIA). "
                "Only recommended for advanced users."
            )
        )
        badges.append(("RT", "warning"))
    if is_xanmod:
        type_parts.append(_("Gaming & performance optimized"))
        full_parts.append(
            _(
                "Tuned for faster gaming and a more responsive desktop. "
                "Great for daily use if you want extra performance."
            )
        )
        badges.append(("Xanmod", "purple"))
    if is_cachyos:
        type_parts.append(_("Performance optimized by CachyOS"))
        full_parts.append(
            _(
                "EEVDF scheduler with LTO, AutoFDO and Propeller optimizations. "
                "Excellent for gaming and desktop responsiveness."
            )
        )
        badges.append(("CachyOS", "purple"))

    if is_big:
        type_parts.append(
            _(
                "BigCommunity kernel (big-kernel), optimized for gaming and general "
                "use (BORE, Clang ThinLTO, Intel fixes)"
            )
        )
        full_parts.append(
            _(
                "Official kernel.org kernel with Manjaro's configuration and "
                "patches, plus the BORE scheduler, Clang + ThinLTO build and "
                "fixes for recent Intel GPUs (Arrow Lake / Meteor Lake)."
            )
        )
        badges.append(("BigCommunity", "accent"))

    # Origin: kernels that don't come from the enabled repositories
    source = kernel.get("source", "")
    if source == "local":
        type_parts.append(_("Package from outside the official repositories"))
        full_parts.append(
            _(
                "Installed from a package that the enabled repositories don't "
                "provide (community or self-built). It is updated by whoever "
                "provides the package, not by system updates."
            )
        )
        badges.append((_("Local"), "accent"))
    elif source == "manual":
        type_parts.append(_("Installed manually, outside the package manager"))
        full_parts.append(
            _(
                "This kernel was not installed by a package, so it can't be "
                "updated or removed here. Manage it the same way it was installed."
            )
        )
        badges.append((_("Manual"), "warning"))

    type_desc = " · ".join(type_parts) if type_parts else _("Latest features & drivers")
    full_desc = (
        " ".join(full_parts)
        if full_parts
        else _("Always up to date with the newest features and hardware support.")
    )

    return KernelTypeInfo(
        is_lts=is_lts,
        is_rt=is_rt,
        is_xanmod=is_xanmod,
        is_cachyos=is_cachyos,
        is_big=is_big,
        type_desc=type_desc,
        full_desc=full_desc,
        badge_entries=badges,
    )


# ------------------------------------------------------------------
# Sort helper
# ------------------------------------------------------------------


def version_sort_key(kernel: dict) -> tuple[int, ...]:
    """Sort key extracting numeric parts from a kernel version string."""
    version = kernel.get("version", "0")
    numbers = re.findall(r"\d+", version)
    return tuple(int(n) for n in numbers[:4]) if numbers else (0,)
