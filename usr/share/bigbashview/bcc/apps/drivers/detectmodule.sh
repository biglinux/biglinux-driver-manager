#!/bin/bash
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
##############
dd-desc.sh
dd-desc.sh
dd-desc.sh
# Detect modules needed
dd-desc.sh
dd-desc.sh
dd-desc.sh
# By Bruno Goncalves < www.biglinux.com.br >
dd-desc.sh
dd-desc.sh
dd-desc.sh
# 2022/03/01
dd-desc.sh
dd-desc.sh
dd-desc.sh
# License GPL V2 or greater
dd-desc.sh
dd-desc.sh
dd-desc.sh
###############
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
OIFS=$IFS
dd-desc.sh
dd-desc.sh
dd-desc.sh
IFS=$'\n'
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    # PCI
dd-desc.sh
dd-desc.sh
dd-desc.sh
    PCI_LIST="$(grep -R : device-ids/ | grep 'pci.ids')"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    # Result example from list
dd-desc.sh
dd-desc.sh
dd-desc.sh
    # device-ids/r8101/pci.ids:10EC:8136
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    for i  in  $(lspci -nn | cut -f2- -d" "); do
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
        ID="$(echo "$i" | rev | cut -f1 -d[ | cut -f2 -d] | rev)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
        TYPE="$(echo "$i" | cut -f1 -d[)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
        NAME="$(echo "$i" | cut -f2- -d: | rev | cut -f2- -d[ | rev)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
        if [ "$(echo "$PCI_LIST" | grep "$ID")" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
            ADDR="$(grep -m1 -R $ID)"  # Example: device-ids/r8101/pci.ids:10EC:8136
dd-desc.sh
dd-desc.sh
dd-desc.sh
            MODULE="$(echo "$ADDR" | cut -f2 -d/)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            PKG="$(cat device-ids/$MODULE/pkg)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "Category: $TYPE"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "Device: $NAME"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "ID: $ID"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "MODULE: $MODULE"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "PKG: $PKG"
dd-desc.sh
dd-desc.sh
dd-desc.sh
        fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    done
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    # USB
dd-desc.sh
dd-desc.sh
dd-desc.sh
    USB_LIST="$(grep -R : device-ids/ | grep 'usb.ids')"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    # Result example from list
dd-desc.sh
dd-desc.sh
dd-desc.sh
    # device-ids/8723bu/usb.ids:20F4:108A
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    for i  in  $(lsusb); do
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
        ID="$(echo "$i" | cut -f6 -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh
        NAME="$(echo "$i" | cut -f7- -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
        if [ "$(echo "$USB_LIST" | grep "$ID")" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
            ADDR="$(grep -m1 -R $ID)"  # Example: device-ids/r8101/pci.ids:10EC:8136
dd-desc.sh
dd-desc.sh
dd-desc.sh
            MODULE="$(echo "$ADDR" | cut -f2 -d/)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            PKG="$(cat device-ids/$MODULE/pkg)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "Device: $NAME"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "ID: $ID"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "MODULE: $MODULE"
dd-desc.sh
dd-desc.sh
dd-desc.sh
            echo "PKG: $PKG"
dd-desc.sh
dd-desc.sh
dd-desc.sh
        fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    done
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
IFS=$OIFS
dd-desc.sh
dd-desc.sh
dd-desc.sh
