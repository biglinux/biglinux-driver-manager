#!/usr/bin/env bash

########################################################
#	Author1: Bruno Goncalves (www.biglinux.com.br)
#	Author2: Rafael Ruscher (rruscher@gmail.com)
#	Date:    2022/02/28
#
#	Description: Control Center to help usage of BigLinux
#
#	Licensed by GPL V2 or greater
########################################################

#Translation
export TEXTDOMAINDIR="/usr/share/locale"
export TEXTDOMAIN=biglinux-driver-manager

#Only to debug
#rm -R "$HOME/.config/bigcontrolcenter/"

# transfet.net
# curl --upload-file "$1" https://transfer.sh | tee "$HOME/.config/bigcontrolcenter-drivers/transfer.url"  | zenity --modal --progress --pulsate --no-cancel --auto-close --text $"Enviando, aguarde...";

# filebin.net
curl --data-binary "@/$1" -H "filename: $(basename "$1")" https://filebin.net | tee "$HOME/.config/bigcontrolcenter-drivers/transfer.url" | zenity --modal --progress --pulsate --no-cancel --auto-close --text $"Enviando, aguarde..."
xdg-open "https://filebin.net/$(cat "$HOME/.config/bigcontrolcenter-drivers/transfer.url" | grep '"id": "' | cut -f4 -d'"')"
