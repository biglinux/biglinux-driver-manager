#!/bin/bash

##############
# Detect modules needed
# By Bruno Goncalves < www.biglinux.com.br >
# 2022/03/01
# License GPL V2 or greater
###############

#Translation
export TEXTDOMAINDIR="/usr/share/locale"
export TEXTDOMAIN=biglinux-driver-manager

OIFS=$IFS
IFS=$'\n'


    # PCI
    PCI_LIST="$(grep -Ri : device-ids/ | grep -i 'pci.ids')"
    # Result example from list
    # device-ids/r8101/pci.ids:10EC:8136

    for i  in  $(lspci -nn | cut -f2- -d" "); do

        ID="$(echo "$i" | rev | cut -f1 -d[ | cut -f2 -d] | rev)"
        TYPE="$(echo "$i" | cut -f1 -d[)"
        NAME="$(echo "$i" | cut -f2- -d: | rev | cut -f2- -d[ | rev)"

        if [ "$(echo "$PCI_LIST" | grep -i "$ID")" != "" ]; then

            ADDR="$(grep -i -m1 -R $ID)"  # Example: device-ids/r8101/pci.ids:10EC:8136
            MODULE="$(echo "$ADDR" | cut -f2 -d/)"
            PKG="$(cat device-ids/$MODULE/pkg)"

            echo "Category: $TYPE"
            echo "Device: $NAME"
            echo "ID: $ID"
            echo "MODULE: $MODULE"
            echo "PKG: $PKG"
        fi

    done



    # USB
    USB_LIST="$(grep -Ri : device-ids/ | grep -i 'usb.ids')"
    # Result example from list
    # device-ids/8723bu/usb.ids:20F4:108A

    for i  in  $(lsusb); do

        ID="$(echo "$i" | cut -f6 -d" ")"
        NAME="$(echo "$i" | cut -f7- -d" ")"

        if [ "$(echo "$USB_LIST" | grep -i "$ID")" != "" ]; then

            ADDR="$(grep -i -m1 -R $ID)"  # Example: device-ids/r8101/pci.ids:10EC:8136
            MODULE="$(echo "$ADDR" | cut -f2 -d/)"
            PKG="$(cat device-ids/$MODULE/pkg)"

            echo "Device: $NAME"
            echo "ID: $ID"
            echo "MODULE: $MODULE"
            echo "PKG: $PKG"
        fi

    done


    # SDIO
    SDIO_LIST="$(grep -Ri : device-ids/ | grep -i 'sdio.ids')"
    # Result example from list
    # device-ids/8723bu/sdio.ids:20F4:108A



    for i  in  $(ls /sys/bus/sdio/devices/ 2>/dev/null); do

        Vendor="$(cat /sys/bus/sdio/devices/$i/vendor | cut -f2 -dx)"
        Device="$(cat /sys/bus/sdio/devices/$i/device | cut -f2 -dx)"

        ID="$Vendor:$Device"
        #NAME="$(echo "$i" | cut -f7- -d" ")"

        if [ "$(echo "$SDIO_LIST" | grep -i "$ID")" != "" ]; then

            ADDR="$(grep -i -m1 -R $ID)"  # Example: device-ids/r8101/pci.ids:10EC:8136
            MODULE="$(echo "$ADDR" | cut -f2 -d/)"
            PKG="$(cat device-ids/$MODULE/pkg)"

            #echo "Device: $NAME"
            echo "ID: $ID"
            echo "MODULE: $MODULE"
            echo "PKG: $PKG"
        fi

    done


IFS=$OIFS
