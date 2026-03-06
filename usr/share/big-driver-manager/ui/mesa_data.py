#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Mesa / Video driver data definitions and utility functions.

Extracted from mesa_page.py to keep the UI module focused on presentation.
"""

import os

from core.package_manager import PackageManager
from utils.i18n import _


# Human-readable names and descriptions for Mesa driver variants
_MESA_HUMAN_NAMES: dict[str, dict[str, str]] = {}

# Short notes for specific MHWD drivers (shown in subtitle)
_DRIVER_NOTES: dict[str, str] = {}

# GPU-specific optional packages grouped by vendor
_GPU_PACKAGES: dict[str, list[dict[str, str]]] = {}

# Packages grouped by *purpose* (not vendor).
_PURPOSE_SECTIONS: list[dict] = []


def _init_driver_notes() -> None:
    """Lazily populate _DRIVER_NOTES (needs gettext)."""
    if _DRIVER_NOTES:
        return
    _DRIVER_NOTES.update(
        {
            # NVIDIA standalone drivers
            "video-nvidia": _(
                "Latest NVIDIA driver — best performance and newest features"
            ),
            "video-nvidia-575xx": _(
                "NVIDIA 575 series — use if the latest driver causes issues"
            ),
            "video-nvidia-570xx": _(
                "NVIDIA 570 series — use if the latest driver causes issues"
            ),
            # Hybrid (laptop with two GPUs: Intel + NVIDIA)
            "video-hybrid-intel-nvidia-prime": _(
                "For Intel + NVIDIA laptops — switches between GPUs to save battery"
            ),
            "video-hybrid-intel-nvidia-575xx-prime": _(
                "For Intel + NVIDIA laptops — NVIDIA 575 series"
            ),
            "video-hybrid-intel-nvidia-570xx-prime": _(
                "For Intel + NVIDIA laptops — NVIDIA 570 series"
            ),
            "video-hybrid-intel-nvidia-470xx-prime": _(
                "For Intel + NVIDIA laptops — NVIDIA 470 (legacy, no Wayland)"
            ),
            "video-hybrid-intel-nvidia-390xx-bumblebee": _(
                "For Intel + NVIDIA laptops — NVIDIA 390 (very old GPUs only)"
            ),
            # Hybrid (laptop with two GPUs: AMD + NVIDIA)
            "video-hybrid-amd-nvidia-prime": _(
                "For AMD + NVIDIA laptops — switches between GPUs to save battery"
            ),
            "video-hybrid-amd-nvidia-575xx-prime": _(
                "For AMD + NVIDIA laptops — NVIDIA 575 series"
            ),
            "video-hybrid-amd-nvidia-570xx-prime": _(
                "For AMD + NVIDIA laptops — NVIDIA 570 series"
            ),
            "video-hybrid-amd-nvidia-470xx-prime": _(
                "For AMD + NVIDIA laptops — NVIDIA 470 (legacy, no Wayland)"
            ),
            # Virtual machine
            "video-virtualmachine": _(
                "Optimized display for virtual machines (VirtualBox, VMware, QEMU/KVM)"
            ),
        }
    )


def _init_purpose_sections() -> None:
    """Lazily populate _PURPOSE_SECTIONS (needs gettext)."""
    if _PURPOSE_SECTIONS:
        return
    _PURPOSE_SECTIONS.extend(
        [
            {
                "id": "gaming",
                "title": _("Gaming & 3D Graphics"),
                "icon": "bkm-vulkan",
                "desc": _(
                    "Vulkan and OpenGL libraries essential for games, "
                    "Steam, Wine/Proton and 3D applications."
                ),
                "packages": [
                    {
                        "name": "vulkan-radeon",
                        "short": _("Vulkan for AMD Radeon GPUs"),
                        "vendors": {"amd"},
                        "cat": "Vulkan",
                    },
                    {
                        "name": "lib32-vulkan-radeon",
                        "short": _(
                            "32-bit Vulkan (AMD) — needed by Steam, "
                            "Wine/Proton and older games"
                        ),
                        "vendors": {"amd"},
                        "cat": "Vulkan",
                    },
                    {
                        "name": "vulkan-intel",
                        "short": _("Vulkan for Intel GPUs"),
                        "vendors": {"intel"},
                        "cat": "Vulkan",
                    },
                    {
                        "name": "lib32-vulkan-intel",
                        "short": _(
                            "32-bit Vulkan (Intel) — needed by Steam, "
                            "Wine/Proton and older games"
                        ),
                        "vendors": {"intel"},
                        "cat": "Vulkan",
                    },
                    {
                        "name": "vulkan-nouveau",
                        "short": _(
                            "Open-source Vulkan for NVIDIA (Nouveau) — "
                            "no proprietary driver needed"
                        ),
                        "vendors": {"nvidia"},
                        "cat": "Vulkan",
                    },
                    {
                        "name": "lib32-mesa",
                        "short": _(
                            "32-bit OpenGL — needed by Steam, Wine/Proton "
                            "and older 32-bit games"
                        ),
                        "vendors": {"amd", "intel", "nvidia"},
                        "cat": "OpenGL",
                    },
                ],
            },
            {
                "id": "video",
                "title": _("Video Playback"),
                "icon": "bkm-video-decode",
                "desc": _(
                    "Hardware-accelerated video decoding (VAAPI/VDPAU). "
                    "Makes videos, streaming and video calls smoother "
                    "while reducing CPU and power usage."
                ),
                "packages": [
                    {
                        "name": "libva-nvidia-driver",
                        "short": _("VAAPI for NVIDIA proprietary driver"),
                        "vendors": {"nvidia"},
                        "cat": "VAAPI",
                    },
                    {
                        "name": "intel-media-driver",
                        "short": _("VAAPI for Intel (Broadwell / Gen 8 and newer)"),
                        "vendors": {"intel"},
                        "cat": "VAAPI",
                    },
                    {
                        "name": "libva-intel-driver",
                        "short": _(
                            "VAAPI for older Intel (Haswell to Coffee Lake / Gen 4–9)"
                        ),
                        "vendors": {"intel"},
                        "cat": "VAAPI",
                    },
                    {
                        "name": "libva-mesa-driver",
                        "short": _("VAAPI for AMD and NVIDIA open-source (Nouveau)"),
                        "vendors": {"amd", "nvidia"},
                        "cat": "VAAPI",
                    },
                    {
                        "name": "mesa-vdpau",
                        "short": _(
                            "VDPAU for AMD/NVIDIA open-source — legacy API being "
                            "replaced by VAAPI and Vulkan. Probably not needed."
                        ),
                        "vendors": {"amd", "nvidia"},
                        "cat": "VDPAU",
                        "recommend": False,
                    },
                ],
            },
            {
                "id": "compute",
                "title": _("GPU Compute (AI / ML)"),
                "icon": "bkm-compute",
                "desc": _(
                    "Your graphics card can do more than display images — "
                    "it can also help with heavy processing tasks. "
                    "These libraries allow programs to use the GPU for "
                    "things like artificial intelligence, video editing, "
                    "3D rendering, image processing and scientific simulations. "
                    "Examples: running local AI assistants (Ollama, LocalAI), "
                    "transcribing audio with Whisper, rendering 3D scenes "
                    "in Blender, applying filters in GIMP or Darktable, "
                    "generating images with Stable Diffusion, "
                    "and running physics simulations."
                ),
                "packages": [
                    {
                        "name": "cuda",
                        "short": _(
                            "NVIDIA CUDA — Ollama, Whisper, Stable Diffusion, Blender"
                        ),
                        "vendors": {"nvidia"},
                        "cat": "Compute",
                    },
                    {
                        "name": "opencl-nvidia",
                        "short": _("OpenCL for NVIDIA — Blender, GIMP, Darktable"),
                        "vendors": {"nvidia"},
                        "cat": "Compute",
                    },
                    {
                        "name": "opencl-mesa",
                        "short": _("OpenCL for AMD — Blender, GIMP, Darktable"),
                        "vendors": {"amd"},
                        "cat": "Compute",
                    },
                    {
                        "name": "intel-compute-runtime",
                        "short": _("OpenCL for Intel — Blender, GIMP, Darktable"),
                        "vendors": {"intel"},
                        "cat": "Compute",
                    },
                ],
            },
        ]
    )


# Packages bundled (provided) by each Mesa variant.
_MESA_BUNDLED: dict[str, frozenset[str]] = {
    "stable": frozenset({"libva-mesa-driver"}),
    "tkg-stable": frozenset(
        {
            "vulkan-intel",
            "vulkan-radeon",
            "vulkan-nouveau",
            "libva-mesa-driver",
            "mesa-vdpau",
            "opencl-mesa",
            "vulkan-swrast",
        }
    ),
    "tkg-git": frozenset(
        {
            "vulkan-intel",
            "vulkan-radeon",
            "vulkan-nouveau",
            "libva-mesa-driver",
            "mesa-vdpau",
            "opencl-mesa",
            "vulkan-swrast",
        }
    ),
}


def _init_mesa_names() -> None:
    """Lazy init so gettext is ready."""
    if _MESA_HUMAN_NAMES:
        return
    _MESA_HUMAN_NAMES.update(
        {
            "stable": {
                "title": _("Stable"),
                "desc": _(
                    "Officially tested by the Mesa team. The safest and most "
                    "reliable choice for everyday use, gaming, and video playback."
                ),
                "badge": _("Recommended"),
                "badge_color": "success",
            },
            "tkg-stable": {
                "title": _("Performance"),
                "desc": _(
                    "Modified version with gaming optimizations for extra "
                    "performance. Reliable for most users but may rarely "
                    "cause instabilities."
                ),
                "badge": _("Performance"),
                "badge_color": "accent",
            },
            "tkg-git": {
                "title": _("Development"),
                "desc": _(
                    "Built from the very latest source code with cutting-edge "
                    "features. Offers the best gaming performance but is the "
                    "least tested — only for advanced users."
                ),
                "badge": "DEV",
                "badge_color": "danger",
            },
            "amber": {
                "title": _("Legacy"),
                "desc": _(
                    "For very old graphics cards that only support OpenGL 2.1 "
                    "or earlier. Only install this if newer Mesa versions "
                    "don't work with your hardware."
                ),
                "badge": _("Legacy"),
                "badge_color": "warning",
            },
        }
    )


# Illustration-style SVG icons directory
_ICONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
    "illustrations",
)

# Row-level SVG icons for Mesa variants
_MESA_ROW_ICONS: dict[str, str] = {
    "amber": "icon_mesa_row_legacy.svg",
    "stable": "icon_mesa_row_stable.svg",
    "tkg-stable": "icon_mesa_row_performance.svg",
    "tkg-git": "icon_mesa_row_development.svg",
}

# Row-level SVG icons for GPU package categories
_CAT_ROW_ICONS: dict[str, str] = {
    "Vulkan": "icon_row_vulkan.svg",
    "VAAPI": "icon_row_video.svg",
    "VDPAU": "icon_row_video.svg",
    "OpenGL": "icon_row_opengl.svg",
    "Compute": "icon_row_compute.svg",
}


def _get_recommendations(
    gpu_vendors: set[str],
    pkg_manager: PackageManager,
    active_mesa: str,
    has_nvidia_proprietary: bool,
    installed_set: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return (missing, installed) recommended packages for detected GPUs.

    Each item: {"name": str, "short": str, "section": str, "cat": str}.

    When *installed_set* is provided it is used directly, avoiding
    subprocess calls via *pkg_manager* (safe for the UI thread).
    """
    _init_purpose_sections()
    bundled = _MESA_BUNDLED.get(active_mesa or "stable", frozenset())
    missing: list[dict] = []
    installed: list[dict] = []

    def _is_installed(name: str) -> bool:
        if installed_set is not None:
            return name in installed_set
        return pkg_manager.is_package_installed(name)

    for section in _PURPOSE_SECTIONS:
        for pkg in section["packages"]:
            if not (pkg["vendors"] & gpu_vendors):
                continue
            if not pkg.get("recommend", True):
                continue
            name = pkg["name"]
            if name in bundled:
                continue
            if name == "libva-nvidia-driver" and not has_nvidia_proprietary:
                continue
            if name in ("cuda", "opencl-nvidia") and not has_nvidia_proprietary:
                continue
            # Hide vulkan-nouveau when NVIDIA proprietary is active
            if name == "vulkan-nouveau" and has_nvidia_proprietary:
                continue
            # Hide mesa-vdpau when neither AMD nor nouveau is active
            has_amd_or_nouveau = "amd" in gpu_vendors or (
                "nvidia" in gpu_vendors and not has_nvidia_proprietary
            )
            if name == "mesa-vdpau" and not has_amd_or_nouveau:
                continue
            # Hide libva-mesa-driver when neither AMD nor nouveau is active
            if name == "libva-mesa-driver" and not has_amd_or_nouveau:
                continue
            entry = {
                "name": name,
                "short": pkg.get("short", ""),
                "section": section["title"],
                "cat": pkg.get("cat", ""),
            }
            if _is_installed(name):
                installed.append(entry)
            else:
                missing.append(entry)

    return missing, installed
