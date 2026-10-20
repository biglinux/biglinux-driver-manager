#!/bin/sh
# SDDM DisplayCommand for gpu mode nvidia: the PRIME setup, then the
# DisplayCommand configured before ours (SDDM takes only one), or SDDM's own
# Xsetup.
conf_dir=${BDM_SDDM_DIR:-/etc}
"${BDM_PRIME_SCRIPT:-/usr/share/big-driver-manager-cli/prime-xrandr.sh}"
previous=$(cat "$conf_dir"/sddm.conf.d/*.conf "$conf_dir/sddm.conf" 2>/dev/null |
    grep -v 'big-driver-manager-cli' |
    sed -n 's/^[[:space:]]*DisplayCommand[[:space:]]*=[[:space:]]*//p' | tail -n 1)
previous=${previous:-/usr/share/sddm/scripts/Xsetup}
if [ -x "${previous%% *}" ]; then
    exec $previous
fi
exit 0
