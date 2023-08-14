#!/bin/bash

#Install .deb packages
#
#Author Bruno Goncalves  <www.biglinux.com.br>
#License: GPLv2 or later
#################################################

#Translation
export TEXTDOMAINDIR="/usr/share/locale"
export TEXTDOMAIN=biglinux-driver-manager

OIFS=$IFS
IFS=$'\n'

if [ "$ACTION" = "install_video_now" ]; then
	MARGIN_TOP_MOVE="-90" WINDOW_HEIGHT=12 PID_BIG_DEB_INSTALLER="$$" WINDOW_ID="$WINDOW_ID" ./install_terminal_resize.sh &
	pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY KDE_SESSION_VERSION=5 KDE_FULL_SESSION=true mhwd -i pci $DRIVER
	if [ "$?" = "0" ]; then
		kdialog --msgbox $"Concluído, reinicie o computador para ativar a configuração do driver." --title $"Driver"
	else
		kdialog --msgbox $"Ocorreu um erro e o driver não pode ser aplicado." --title $"Driver"
	fi
fi

if [ "$ACTION" = "remove_video_now" ]; then
	MARGIN_TOP_MOVE="-90" WINDOW_HEIGHT=12 PID_BIG_DEB_INSTALLER="$$" WINDOW_ID="$WINDOW_ID" ./install_terminal_resize.sh &
	pkexec env DISPLAY=$DISPLAY XAUTHORITY=$XAUTHORITY KDE_SESSION_VERSION=5 KDE_FULL_SESSION=true mhwd -r pci $DRIVER
	if [ "$?" = "0" ]; then
		kdialog --msgbox $"Concluído, reinicie o computador para ativar a configuração do driver." --title $"Driver"
	else
		kdialog --msgbox $"Ocorreu um erro e o driver não pode ser aplicado." --title $"Driver"
	fi
fi

if [ "$(xwininfo -id $WINDOW_ID 2>&1 | grep -i "No such window")" != "" ]; then
	kill -9 $PID_BIG_DEB_INSTALLER
	exit 0
fi

IFS=$OIFS
