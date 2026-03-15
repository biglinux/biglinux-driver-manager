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
