#!/bin/sh
# NVIDIA as the Xorg primary GPU (big-driver-manager-cli gpu mode nvidia).
# A laptop panel is wired to the integrated GPU: make its outputs show what
# NVIDIA renders. Nothing to do on Wayland or without both providers.
[ "${XDG_SESSION_TYPE:-x11}" = x11 ] || exit 0
command -v xrandr >/dev/null 2>&1 || exit 0
providers=$(xrandr --listproviders 2>/dev/null) || exit 0
# Provider IDs, not names: some names contain spaces.
nvidia=$(printf '%s\n' "$providers" | grep '^Provider' | grep 'name:NVIDIA' |
    sed -n 's/.*id: \(0x[0-9a-fA-F]*\).*/\1/p' | head -n 1)
other=$(printf '%s\n' "$providers" | grep '^Provider' | grep -v 'name:NVIDIA' |
    sed -n 's/.*id: \(0x[0-9a-fA-F]*\).*/\1/p' | head -n 1)
[ -n "$nvidia" ] && [ -n "$other" ] || exit 0
xrandr --setprovideroutputsource "$other" "$nvidia"
xrandr --auto
exit 0
