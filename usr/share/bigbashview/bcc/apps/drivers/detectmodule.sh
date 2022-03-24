#!/bin/bash

##############
# Detect modules needed
# By Bruno Goncalves < www.biglinux.com.br >
# 2022/03/01
# License GPL V2 or greater
###############

OIFS=$IFS
IFS=$'\n'


    # PCI
    PCI_LIST="$(grep -R : device-ids/ | grep 'pci.ids')"
    # Result example from list
    # device-ids/r8101/pci.ids:10EC:8136

    for i  in  $(lspci -nn | cut -f2- -d" "); do

        ID="$(echo "$i" | rev | cut -f1 -d[ | cut -f2 -d] | rev)"
        TYPE="$(echo "$i" | cut -f1 -d[)"
        NAME="$(echo "$i" | cut -f2- -d: | rev | cut -f2- -d[ | rev)"

        if [ "$(echo "$PCI_LIST" | grep "$ID")" != "" ]; then

            ADDR="$(grep -m1 -R $ID)"  # Example: device-ids/r8101/pci.ids:10EC:8136
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
    USB_LIST="$(grep -R : device-ids/ | grep 'usb.ids')"
    # Result example from list
    # device-ids/8723bu/usb.ids:20F4:108A

    for i  in  $(lsusb); do

        ID="$(echo "$i" | cut -f6 -d" ")"
        NAME="$(echo "$i" | cut -f7- -d" ")"

        if [ "$(echo "$USB_LIST" | grep "$ID")" != "" ]; then

            ADDR="$(grep -m1 -R $ID)"  # Example: device-ids/r8101/pci.ids:10EC:8136
            MODULE="$(echo "$ADDR" | cut -f2 -d/)"
            PKG="$(cat device-ids/$MODULE/pkg)"

            echo "Device: $NAME"
            echo "ID: $ID"
            echo "MODULE: $MODULE"
            echo "PKG: $PKG"
        fi

    done


IFS=$OIFS
