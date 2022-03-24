#!/bin/bash


if [ "$ACTION" = "install_pkg_pamac" ]; then


pacman -Si $DRIVER

    if [ "$?" = "0" ]; then

        pamac-installer $DRIVER &
    else
        pamac-installer --build $DRIVER &

    fi

fi

if [ "$ACTION" = "remove_pkg_pamac" ]; then

    pamac-installer --remove $DRIVER &

fi


PID="$!"

if [ "$PID" = "" ]; then
    exit
fi

CONTADOR=0
while [  $CONTADOR -lt 100 ]; do
    if [ "$(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ")" != "" ]; then
        xsetprop -id=$(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") --atom WM_TRANSIENT_FOR --value $(wmctrl -p -l -x | grep Big-Driver-Manager$ | cut -f1 -d" ") -f 32x
        wmctrl -i -r $(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") -b add,skip_pager,skip_taskbar
        wmctrl -i -r $(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") -b toggle,modal
        break
    fi

    sleep 0.1
    let CONTADOR=CONTADOR+1; 
done

wait
