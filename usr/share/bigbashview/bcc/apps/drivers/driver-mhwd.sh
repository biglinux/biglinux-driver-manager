#!/usr/bin/env bash
#shellcheck disable=SC2155,SC2034
#shellcheck source=/dev/null

#  /usr/share/bigbashview/bcc/apps/drivers/driver-mhwd.sh
#  Description: Control Center to help usage of BigLinux
#
#  Created: 2022/02/28
#  Altered: 2023/08/18
#
#  Copyright (c) 2023-2023, Vilmar Catafesta <vcatafesta@gmail.com>
#                2022-2023, Bruno Gonçalves <www.biglinux.com.br>
#                2022-2023, Rafael Ruscher <rruscher@gmail.com>
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#  1. Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
#  THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
#  IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
#  OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
#  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
#  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
#  NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
#  DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
#  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
#  THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

APP="${0##*/}"
_VERSION_="1.0.0-20230818"
export BOOTLOG="/tmp/biglinux-driver-manager-$USER-$(date +"%d%m%Y").log"
export LOGGER='/dev/tty8'
LIBRARY=${LIBRARY:-'/usr/share/bigbashview/bcc/shell'}
[[ -f "${LIBRARY}/bcclib.sh" ]] && source "${LIBRARY}/bcclib.sh"
[[ -f "${LIBRARY}/bstrlib.sh" ]] && source "${LIBRARY}/bstrlib.sh"

function sh_config {
	#Translation
	export TEXTDOMAINDIR="/usr/share/locale"
	export TEXTDOMAIN=biglinux-driver-manager

	OIFS=$IFS
	IFS=$'\n'
}

function sh_main {
	rm -f $HOME/.config/bigcontrolcenter-drivers/cache_video_*.html

	SHOW_DRIVER() {
		# $CATEGORY
		# $VIDEO_DRIVER_NAME
		# $VIDEO_DRIVER_ENABLED
		# $VIDEO_DRIVER_COMPATIBLE
		# $VIDEO_DRIVER_OPEN

		if [ "$VIDEO_DRIVER_OPEN" = "true" ]; then
			OPEN_OR_PROPRIETARY=$"Este driver é software livre."
		else
			OPEN_OR_PROPRIETARY=$"Este driver é proprietário."
		fi

		if [ "$VIDEO_DRIVER_COMPATIBLE" = "true" ]; then
			DRIVER_COMPATIBLE=$"Este driver parece compatível com este computador."
		else
			DRIVER_COMPATIBLE=""
		fi

		if [ "$VIDEO_DRIVER_ENABLED" = "true" ]; then
			DRIVER_ENABLE_OR_DISABLE=$"Remover"
			INSTALL_OR_REMOVE_VIDEO="remove_video_now"
			DISABLED_BUTTON="remove-button"
			DISABLED_MESSAGE=""
		else
			DRIVER_ENABLE_OR_DISABLE=$"Instalar"
			INSTALL_OR_REMOVE_VIDEO="install_video_now"
			if [ "$VIDEO_DRIVER_NVIDIA_ENABLED" = "true" ] && [ "$(echo "$VIDEO_DRIVER_NAME" | grep nvidia)" != "" ]; then
				DISABLED_BUTTON="disabled"
				DRIVER_ENABLE_OR_DISABLE=$"Desativado"
				DISABLED_MESSAGE=$"Antes de instalar este driver, remova o outro driver Nvidia."
				#DRIVER_ENABLE_OR_DISABLE=$"Já existe outro driver nVidia instalado, para instalar este driver, remova primeiro o driver instalado."
			else
				INSTALL_OR_REMOVE_VIDEO="install_video_now"
				DISABLED_BUTTON=""
				DISABLED_MESSAGE=""
			fi

		fi
#		VIDEO_DRIVER_NAME_CLEAN="$(echo "$VIDEO_DRIVER_NAME" | sed 's|-| |g')"
		VIDEO_DRIVER_NAME_CLEAN=${VIDEO_DRIVER_NAME//-/ }

		if [ "$VIDEO_DRIVER_NAME_CLEAN" = "video nvidia" ]; then
			VIDEO_DRIVER_NAME_CLEAN="video nvidia $(LC_ALL=C pacman -Si nvidia-utils | grep "^Version" | cut -f2 -d":" | sed 's|\..*|xx|g')"
		fi

		cat <<-EOF >>"$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
			<div class="app-card $CATEGORY">
			<span class="icon-cat icon-category-$CATEGORY" style="display:table-cell;"></span><span class="titlespan" style="display:table-cell;">
			$VIDEO_DRIVER_NAME_CLEAN
			</span>
			<div class="app-card__subtext">
			$OPEN_OR_PROPRIETARY
			<br>
			<br>
			$DESC
			$DISABLED_MESSAGE
			</div>
		EOF

		cat <<-EOF >>"$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
			<div class="app-card-buttons">
			<a class="content-button status-button  $DISABLED_BUTTON" $DISABLED_BUTTON" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_VIDEO}=${VIDEO_DRIVER_NAME}">
			$DRIVER_ENABLE_OR_DISABLE
			</a>
			</div>
			</div>
		EOF
	}

	# MHWD import info OPEN, used to video drivers
	##############################################

	# If module is proprietary show false
	# Result example: video-nvidia-470xx false
	VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE="$(mhwd -la | awk '{ print $1 " " $3 }' | grep -e video- -e network-)"

	# Show compatible with this hardware
	VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE="$(mhwd -l | awk '{ print $1 }' | grep -e video- -e network-)"

	# Show if installed
	VIDEO_DRIVER_ENABLED_LIST="$(mhwd -li | awk '{ print $1 }' | grep -e video- -e network-)"

	# Show if nvidia driver is enabled
	if [ "$(echo "$VIDEO_DRIVER_ENABLED_LIST" | grep -i nvidia)" != "" ]; then
		VIDEO_DRIVER_NVIDIA_ENABLED="true"
	fi

	for i in $VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE; do
		VIDEO_DRIVER_NAME="$(echo "$i" | cut -f1 -d" ")"
		VIDEO_DRIVER_OPEN="$(echo "$i" | cut -f2 -d" ")"

		if [ "$(echo "$VIDEO_DRIVER_ENABLED_LIST" | grep "^$VIDEO_DRIVER_NAME$")" != "" ]; then
			VIDEO_DRIVER_ENABLED="true"
		else
			VIDEO_DRIVER_ENABLED="false"
		fi

		if [ "$(echo "$VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE" | grep -ve video-linux -ve video-modesetting -ve video-vesa | grep "^$VIDEO_DRIVER_NAME$")" != "" ]; then
			VIDEO_DRIVER_COMPATIBLE="true"
			if [ "$(echo "$VIDEO_DRIVER_NAME" | grep network)" != "" ]; then
				CATEGORY="wifi Star"
				if [ "$(echo "$VIDEO_DRIVER_NAME" | grep 8168)" != "" ]; then
					CATEGORY="ethernet Star"
				fi
			else
				CATEGORY="Gpu Star"
			fi
		else
			VIDEO_DRIVER_COMPATIBLE="false"
			if [ "$(echo "$VIDEO_DRIVER_NAME" | grep network)" != "" ]; then
				CATEGORY="wifi"
				if [ "$(echo "$VIDEO_DRIVER_NAME" | grep 8168)" != "" ]; then
					CATEGORY="ethernet"
				fi
			else
				CATEGORY="Gpu"
			fi
		fi
		SHOW_DRIVER "$VIDEO_DRIVER_NAME" "$VIDEO_DRIVER_ENABLED" "$VIDEO_DRIVER_COMPATIBLE" "$VIDEO_DRIVER_OPEN"
	done
	IFS=$OIFS
}

#sh_debug
sh_config
sh_main
