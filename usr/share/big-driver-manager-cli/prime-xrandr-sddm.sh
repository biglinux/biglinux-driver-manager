#!/bin/sh
# SDDM DisplayCommand for gpu mode nvidia: the PRIME setup, then SDDM's own
# Xsetup, which DisplayCommand replaces.
/usr/share/big-driver-manager-cli/prime-xrandr.sh
if [ -x /usr/share/sddm/scripts/Xsetup ]; then
    exec /usr/share/sddm/scripts/Xsetup
fi
exit 0
