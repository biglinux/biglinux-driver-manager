#!/bin/bash

Package="$1"
Kernel_version="$2"

OIFS=$IFS
# kernel current version like mhwd
IFS=. read -r major minor _ <<< "$(uname -r)"
if uname -r | grep xanmod > /dev/null; then current="linux-xanmod"; else current="linux$major$minor"; fi
IFS=$'\n'

for pkg in $(pacman -Qqs "$current"); do
    pkg=${pkg//$current/$Kernel_version}
    [[ -n $(pacman -Ssq "^$pkg$" | grep -E "^$pkg$|^$pkg-\S+$") ]] && pkginstall+=("$pkg")
done

# pacman -Syy
# pacman --noconfirm --overwrite \* -S "${pkginstall[@]}"


if [ "$Package" = "install" ]; then
    pamac-installer ${pkginstall[@]} &
fi


if [ "$Package" = "remove" ]; then
#     pamac-installer --remove $(pacman -Qqs "$Kernel_version") &
    pamac-installer --remove $Kernel_version $(LC_ALL=C timeout 10s pamac remove -odc $Kernel_version | grep "^  " | cut -f3 -d" ") &
fi


PID="$!"

if [ "$PID" = "" ]; then
    exit
fi

CONTADOR=0
while [  $CONTADOR -lt 100 ]; do
    if [ "$(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ")" != "" ]; then
        xsetprop -id=$(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") --atom WM_TRANSIENT_FOR --value $(wmctrl -p -l -x | grep Big-Kernel-Manager$ | cut -f1 -d" ") -f 32x
        wmctrl -i -r $(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") -b add,skip_pager,skip_taskbar
        wmctrl -i -r $(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") -b toggle,modal
        break
    fi

    sleep 0.1
    let CONTADOR=CONTADOR+1; 
done

wait
