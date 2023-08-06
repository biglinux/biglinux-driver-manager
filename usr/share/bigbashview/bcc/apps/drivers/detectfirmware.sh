#!/usr/bin/env bash
#shellcheck disable=SC2155
#shellcheck source=/dev/null

#  usr/share/bigbashview/bcc/apps/drivers/detectfirmware.sh
#	Description: Detect firmware needed
#  Created: 2022/03/01
#  Altered: 2023/07/26
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
_VERSION_="1.0.0-20230726"
LIBRARY=${LIBRARY:-'/usr/share/bigbashview/bcc/shell'}
[[ -f "${LIBRARY}/bcclib.sh" ]] && source "${LIBRARY}/bcclib.sh"

function sh_config {
	#Translation
	export TEXTDOMAINDIR="/usr/share/locale"
	export TEXTDOMAIN=biglinux-driver-manager
	declare -g OIFS=$IFS
	declare -g INSTALLED_PKGS="$(sh_installed_pkgs)"
	IFS=$'\n'
}

function SHOW_DRIVER {
	# $CATEGORY
	# $VIDEO_DRIVER_NAME
	# $VIDEO_DRIVER_ENABLED
	# $VIDEO_DRIVER_COMPATIBLE
	# $VIDEO_DRIVER_OPEN

	OPEN_OR_PROPRIETARY=$([ "$VIDEO_DRIVER_OPEN" = "true" ] && echo $"Este driver é software livre." || echo $"Este driver é proprietário.")
	DRIVER_COMPATIBLE=$([ "$VIDEO_DRIVER_COMPATIBLE" = "true" ] && echo $"Este driver parece compatível com este computador." || echo "")

	if [ "$VIDEO_DRIVER_ENABLED" = "true" ]; then
	    DRIVER_ENABLE_OR_DISABLE=$"Remover"
	    INSTALL_OR_REMOVE_VIDEO="remove_video_now"
	    DISABLE_BUTTON="false"
	else
	    DRIVER_ENABLE_OR_DISABLE=$"Instalar"
	    INSTALL_OR_REMOVE_VIDEO="install_video_now"
	    DISABLE_BUTTON=$([ "$VIDEO_DRIVER_NVIDIA_ENABLED" = "true" ] && [[ "$VIDEO_DRIVER_NAME" =~ nvidia ]] && echo "true" || echo "false")
	    [ "$DISABLE_BUTTON" = "true" ] && DRIVER_ENABLE_OR_DISABLE=$"Já existe outro driver nVidia instalado, para instalar este driver, remova primeiro o driver instalado."
	fi
	VIDEO_DRIVER_NAME_CLEAN="${VIDEO_DRIVER_NAME//-/ }"

cat <<-EOF >>"$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
	<div class="app-card $CATEGORY">
	<span>
	$VIDEO_DRIVER_NAME_CLEAN
	</span>
	<div class="app-card__subtext">
	$OPEN_OR_PROPRIETARY
	<br><br>
	$DESC
	$DRIVER_COMPATIBLE
	</div>
EOF

	if [ "$DISABLE_BUTTON" = "false" ]; then
cat <<-EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
		<div class="app-card-buttons">
		<a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_VIDEO}=${VIDEO_DRIVER_NAME}">$DRIVER_ENABLE_OR_DISABLE</a>
		</div>
		</div>
EOF
	else
cat <<-EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
		<div class="app-card-buttons">
		$DRIVER_ENABLE_OR_DISABLE
		</div>
		</div>
EOF
	fi
}

function SHOW_MODULE {
	# $PKG
	# $MODULE
	# $NAME
	# $ID
	# $CATEGORY
	# $MODULE_COMPATIBLE
	# $MODULE_LOADED
	# $PKG_INSTALLED

	DRIVER_COMPATIBLE=$([ "$MODULE_COMPATIBLE" = "true" ] && echo $"Este driver parece compatível com este computador." || echo "")
	PKG_INSTALLED_OR_NOT=$([ "$PKG_INSTALLED" = "true" ] && echo $"Remover" || echo $"Instalar")
	INSTALL_OR_REMOVE_PKG=$([ "$PKG_INSTALLED" = "true" ] && echo "remove_video_now" || echo "install_video_now")

cat <<-EOF >>"$HOME/.config/bigcontrolcenter-drivers/cache_module_$PKG.html"
	<div class="app-card $CATEGORY">
	<span><svg viewBox="0 0 512 512">
	<path fill="currentColor" d="M204.3 5C104.9 24.4 24.8 104.3 5.2 203.4c-37 187 131.7 326.4 258.8 306.7 41.2-6.4 61.4-54.6 42.5-91.7-23.1-45.4 9.9-98.4 60.9-98.4h79.7c35.8 0 64.8-29.6 64.9-65.3C511.5 97.1 368.1-26.9 204.3 5zM96 320c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm32-128c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm128-64c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm128 64c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32z" />
	</svg>
	$MODULE
	</span>
	<div class="app-card__subtext">
	$DESC
	$DRIVER_COMPATIBLE
	</div>
	<div class="app-card-buttons">
	<a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_PKG}=${PKG}">
	$PKG_INSTALLED_OR_NOT
	</a></div></div>
EOF
}

function sh_init {
	# MHWD import info OPEN, used to video drivers
	###################################
	# If module is proprietary show false
	# Result example: video-nvidia-470xx false
	VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE="$(mhwd -la | awk '{ print $1 " " $3 }' | grep -i video-)"

	# Show compatible with this hardware
	VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE="$(mhwd -l | awk '{ print $1 }' | grep -i video-)"

	# Show if installed
	VIDEO_DRIVER_ENABLED_LIST="$(mhwd -li | awk '{ print $1 }' | grep -i video-)"

	# Show if nvidia driver is enabled
	if [[ "$VIDEO_DRIVER_ENABLED_LIST" =~ [nN]vidia ]]; then
		VIDEO_DRIVER_NVIDIA_ENABLED="true"
	fi

	for i in $VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE; do
		VIDEO_DRIVER_NAME="${i%% *}"
		VIDEO_DRIVER_OPEN="${i#* }"
		VIDEO_DRIVER_ENABLED=$(grep -q -i "^$VIDEO_DRIVER_NAME$" <<< "$VIDEO_DRIVER_ENABLED_LIST" && echo "true" || echo "false")

		if grep -Eqvi 'video-linux|video-modesetting|video-vesa' <<< "$VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE" && grep -qi "^$VIDEO_DRIVER_NAME$" <<< "$VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE"; then
		    VIDEO_DRIVER_COMPATIBLE="true"
		    CATEGORY="Gpu Star"
		else
		    VIDEO_DRIVER_COMPATIBLE="false"
		    CATEGORY="Gpu"
		fi

		SHOW_DRIVER "$VIDEO_DRIVER_NAME" "$VIDEO_DRIVER_ENABLED" "$VIDEO_DRIVER_COMPATIBLE" "$VIDEO_DRIVER_OPEN"
	done

	# Other modules from BigLinux Scripts, using PCI
	################################################
	# PCI
	#PCI_LIST="$(grep -Ri : device-ids/ | grep -i 'pci.ids')"
	PCI_LIST="$(grep -Ri 'device-ids/.*pci.ids' *)"
	# Result example from list
	# device-ids/r8101/pci.ids:10EC:8136
#	PCI_IN_PC="$(lspci -nn | cut -f2- -d" ")"
	PCI_IN_PC=$(lspci -nn | while read -r num dev; do echo "${dev#* }"; done)
#	PCI_LIST_MODULES="$(echo "$PCI_LIST" | cut -f2 -d/ | sort -u)"
	PCI_LIST_MODULES=$(awk -F'/' '{print $2}' <<< "$PCI_LIST" | sort -u)

	for MODULE in $PCI_LIST_MODULES; do
		ID_LIST="$(echo "$PCI_LIST" | grep -i "/$MODULE/" | rev | cut -f1,2 -d: | rev)"
		CATEGORY="$(cat device-ids/$MODULE/category)"
		PKG="$(cat device-ids/$MODULE/pkg)"
		DESC="$(cat device-ids/$MODULE/description)"
		MODULE_COMPATIBLE="false"

		for i in $ID_LIST; do
			if [ "$(echo "$PCI_IN_PC" | grep -i "$i")" != "" ]; then
				NAME="$(echo "$PCI_IN_PC" | grep -i "$ID" | cut -f2- -d" ")"
				MODULE_COMPATIBLE="true"
				CATEGORY="$CATEGORY Star"
			fi
		done

		MODULE_LOADED="false"
		if modinfo -n "$MODULE" &> /dev/null; then
		    MODULE_LOADED="true"
		fi

		if [ "$(echo "$INSTALLED_PKGS" | grep -i ^$PKG$)" != "" ]; then
			PKG_INSTALLED="true"
		else
			PKG_INSTALLED="false"
		fi
		SHOW_MODULE "$PKG" "$MODULE" "$NAME" "$ID" "$CATEGORY" "$MODULE_COMPATIBLE" "$MODULE_LOADED" "$PKG_INSTALLED" "$DESC"
	done

	# PCI
	PCI_LIST="$(grep -Ri : device-ids/ | grep -i 'pci.ids')"
	# Result example from list
	# device-ids/r8101/pci.ids:10EC:8136
	PCI_IN_PC="$(lspci -nn | cut -f2- -d" ")"
	PCI_LIST_MODULES="$(echo "$PCI_LIST" | cut -f2 -d/ | sort -u)"

	for MODULE in $PCI_LIST_MODULES; do
		ID_LIST="$(echo "$PCI_LIST" | grep -i "/$MODULE/" | rev | cut -f1,2 -d: | rev)"
		CATEGORY="$(cat device-ids/$MODULE/category)"
		PKG="$(cat device-ids/$MODULE/pkg)"
		DESC="$(cat device-ids/$MODULE/description)"
		MODULE_COMPATIBLE="false"

		for i in $ID_LIST; do
			if [ "$(echo "$PCI_IN_PC" | grep -i "$i")" != "" ]; then
				NAME="$(echo "$PCI_IN_PC" | grep -i "$ID" | cut -f2- -d" ")"
				MODULE_COMPATIBLE="true"
				CATEGORY="$CATEGORY Star"
			fi
		done

		MODULE_LOADED=$(lsmod | grep -q -i "^$MODULE$" && echo "true" || echo "false")
		PKG_INSTALLED=$(grep -q -i "^$PKG$" <<< "$INSTALLED_PKGS" && echo "true" || echo "false")

		SHOW_MODULE "$PKG" "$MODULE" "$NAME" "$ID" "$CATEGORY" "$MODULE_COMPATIBLE" "$MODULE_LOADED" "$PKG_INSTALLED" "$DESC"
	done
	IFS=$OIFS
}

#sh_debug
sh_config
sh_init
