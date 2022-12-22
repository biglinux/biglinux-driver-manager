#!/bin/bash




if [ "$1" = "install" ]; then
    pamac-installer $2 &
fi

if [ "$1" = "remove" ]; then
    pamac-installer --remove $2 &
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
