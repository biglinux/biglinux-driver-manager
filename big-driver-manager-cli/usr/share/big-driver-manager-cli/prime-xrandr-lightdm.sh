#!/bin/sh
# LightDM display-setup-script for gpu mode nvidia. LightDM takes a single
# display-setup-script per seat, so the one configured before ours (e.g. a
# wallpaper sync) still runs, after the PRIME setup.
conf_dir=${BDM_LIGHTDM_DIR:-/etc/lightdm}
"${BDM_PRIME_SCRIPT:-/usr/share/big-driver-manager-cli/prime-xrandr.sh}"
previous=$(cat "$conf_dir/lightdm.conf" "$conf_dir"/lightdm.conf.d/*.conf 2>/dev/null |
    grep -v 'big-driver-manager-cli' |
    sed -n 's/^[[:space:]]*display-setup-script[[:space:]]*=[[:space:]]*//p' | tail -n 1)
if [ -n "$previous" ] && [ -x "${previous%% *}" ]; then
    exec $previous
fi
exit 0
