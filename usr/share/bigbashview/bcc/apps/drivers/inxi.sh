#!/usr/bin/env bash
#shellcheck disable=SC2155
#shellcheck source=/dev/null

#  inxi.sh
#  Created: 0000/00/00
#  Altered: 2023/07/20
#
#  Copyright (c) 2023-2023, Vilmar Catafesta <vcatafesta@gmail.com>
#                0000-2023, bigbruno Bruno Gonçalves <bruno@biglinux.com.br>
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

readonly APP="${0##*/}"
readonly _VERSION_="1.0.0-20230722"
readonly LIBRARY=${LIBRARY:-'/usr/share/bigbashview/bcc/shell'}
[[ -f "${LIBRARY}/bcclib.sh" ]] && source "${LIBRARY}/bcclib.sh"

function sh_config {
	#Translation
	export TEXTDOMAINDIR="/usr/share/locale"
	export TEXTDOMAIN=biglinux-driver-manager
	declare -g DEVICE_INFO=$"Ver informações do dispositivo no Linux Hardware"
	declare -g PCI_IDS="$(lspci -n | cut -f3 -d" ")"
	declare -g USB_IDS="$(lsusb | cut -f6 -d" ")"
	declare -gA AHardInfo
	declare -i lshow=0
}

function sh_remove_tmp_files {
	rm -f /tmp/hardwareinfo-inxi-*.html >/dev/null 2>&-
	rm -f /tmp/hardwareinfo-dmesg.html >/dev/null 2>&-
}

function sh_splitarray {
	local str=("$1")
	local pos="$2"
	local sep="${3:-'|'}"
	local array

	[[ $# -eq 3 && "$pos" = "|" && "$sep" =~ ^[0-9]+$ ]] && { sep="$2"; pos="$3";}
	[[ $# -eq 2 && "$pos" = "$sep"                    ]] && { sep="$pos"; pos=1;}
	[[ $# -eq 1 || ! "$pos" =~ ^[0-9]+$               ]] && { pos=1; }

	IFS="$sep" read -r -a array <<< "${str[@]}"
	echo "${array[pos-1]}"
}

function SHOW_HARDINFO {
	local category_inxi="$1"
	local parameter_inxi="$2"
	local category="$3"
	local name="$4"
	local icon="$5"
	local pkexec="$6"
	local show="$7"
	local cfile="/tmp/hardwareinfo-inxi-$category_inxi.html"

	{
		echo "<div class=\"app-card $category\" style=\"max-height: 100%;\">"
		echo "<div class=\"app-card__title\">$name</div>"
		echo '<div class="app-card__subtext">'
	} >>"$cfile"

	exec $pkexec inxi "$parameter_inxi" "$category_inxi" -y 100 --indents 5 \
		| iconv -t UTF-8 2>- \
		| grep '     ' \
		| sed 's|          ||g' \
		| tr '\n ' ' ' \
		| sed 's|      |\n     |g' \
		| ansi2html -f 18px -l \
		| sed 's|           <span class="|<span class="subcategory1 |g' \
		| grep -A 9999 '<pre class="ansi2html-content">' \
		| grep -v '</html>' \
		| grep -v '</body>' \
		| sed 's|<pre class="ansi2html-content">||g;s|</pre>||g;s|<span class="ansi1 ansi34">|<br><span class="ansi1 ansi34">|g;s|     |</div><div class=hardwareSpace>|g;s|</div><br><span class="ansi1 ansi34">|</div><span class="hardwareTitle2">|g' \
		| sed 's|<span class="ansi1 ansi34">System Temperatures:|<span class="ansi1 ansi33">System Temperatures|g'\
		| sed 's|<span class="ansi1 ansi34">Fan Speeds (RPM):|<span class="ansi1 ansi33">Fan Speeds (RPM)|g' \
		| sed 's|<span class="ansi1 ansi34">Local Storage:|<span class="ansi1 ansi33">Local Storage|g' \
		| sed 's|<span class="ansi1 ansi34">RAM:|<span class="ansi1 ansi33">RAM|g' \
		| sed 's|<span class="ansi1 ansi34">Info:|<span class="ansi1 ansi33">Info|g' \
		| sed 's|<span class="ansi1 ansi34">Topology:|<span class="ansi1 ansi33">Topology|g' \
		| sed 's|<span class="ansi1 ansi34">Speed (MHz):|<span class="ansi1 ansi33">Speed (MHz)|g' \
		>> "$cfile"

	echo '</div></div>' >>"$cfile"

	for i in $(grep -i Chip-ID "$cfile" | sed 's| <br><span class="ansi1 ansi34">class-ID.*||g' | rev | cut -f1 -d" " | rev | sort -u); do
		if [ "$(echo "$PCI_IDS" | grep "$i")" != "" ]; then
			sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run pci:$(echo $i | sed 's|:|-|g')')\">$DEVICE_INFO</a></div>|g" "$cfile"
		elif [ "$(echo "$USB_IDS" | grep "$i")" != "" ]; then
			sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run usb:$(echo $i | sed 's|:|-|g')')\">$DEVICE_INFO</a></div>|g" "$cfile"
		fi
	done
}

function sh_set_show {
	[[ "$1" = "show" ]] && lshow=1
}

function sh_get_parameters {
	if (( lshow )); then
		echo '-c 2 -a -xx --'
	else
		echo '-c 2 -x -z --'
	fi
}

function sh_set_hardinfo {
	AHardInfo=()
	AHardInfo+=(['cpu']="$(sh_get_parameters)|cpu|$'Processador'|cpu|''|$lshow")

	#Clean CPU
	grep -ve 'Vulnerabilities:' -ve 'Type:' /tmp/hardwareinfo-inxi-cpu.html >/tmp/hardwareinfo-inxi-cpu2.html
	mv -f /tmp/hardwareinfo-inxi-cpu2.html /tmp/hardwareinfo-inxi-cpu.html

	AHardInfo+=(['machine']="$(sh_get_parameters)|machine|$'Placa mãe'|machine|''|$lshow")
	AHardInfo+=(['memory']="$(sh_get_parameters)|memory|$'Memória'|memory|''|$lshow")
	AHardInfo+=(['swap']="$(sh_get_parameters)|memory|$'Swap Memória Virtual'|swap|''|$lshow")
:<<'comment'
	AHardInfo+=(['graphics']="$(sh_get_parameters)|gpu|$'Placa de vídeo'|graphics|"pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY"|$lshow")
	AHardInfo+=(['audio']="$(sh_get_parameters)|audio|\$'Áudio'|audio|''|$lshow")
	AHardInfo+=(['network-advanced']="$(sh_get_parameters)|Network|\$'Rede'|network|''|$lshow")
	AHardInfo+=(['ip']="$(sh_get_parameters)|network|\$'Conexões de Rede'|ip|''|$lshow")
	AHardInfo+=(['usb']="$(sh_get_parameters)|usb|\$'Dispositivos e conexões USB"|usb|''|$lshow")
	AHardInfo+=(['slots']="$(sh_get_parameters)|pci|\$'Portas PCI'|usb|''|$lshow")
	AHardInfo+=(['battery']="$(sh_get_parameters)|battery|\$'Bateria'|battery|''|$lshow")
	AHardInfo+=(['disk-full']="$(sh_get_parameters)|disk|\$'Dispositivos de Armazenamento'|'disk'|''|$lshow")
	AHardInfo+=(['partitions-full']="$(sh_get_parameters)|disk|$'Partições montadas'|disk|''|$lshow")
	AHardInfo+=(['unmounted']="$(sh_get_parameters)|disk|$'Partições desmontadas'|disk|"pkexec -u $BIGUSER"|$lshow")

	# Save dmesg
	dmesg -t --level=alert,crit,err,warn >/tmp/hardwareinfo-dmesg.html

	AHardInfo+=(['logical']="$(sh_get_parameters)|disk|$'Dispositivos lógicos'|disk|''|$lshow")
	AHardInfo+=(['raid']="$(sh_get_parameters)|disk|\$'Raid'|disk|''|$lshow")
	AHardInfo+=(['system']="$(sh_get_parameters)|system|\$'Sistema'|disk|''|$lshow")
	AHardInfo+=(['info']="$(sh_get_parameters)|system|\$'Informações de Sistema|disk|''|$lshow")
	AHardInfo+=(['repos']="$(sh_get_parameters)|system|$'Repositórios'|disk|''|$lshow")
	AHardInfo+=(['bluetooth']="$(sh_get_parameters)|bluetooth|$'Bluetooth'|disk|''|$lshow")
	AHardInfo+=(['sensors']="$(sh_get_parameters)|sensors|\$'Temperatura'|disk|"pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY"|$lshow")
comment
}

function sh_process_hardinfo {
	local category_inxi
	local parameter_inxi
	local category
	local name
	local icon
	local pkexec
	local show

	for i in "${!AHardInfo[@]}"; {
		category_inxi="$i"
		parameter_inxi="$(sh_splitarray "${AHardInfo[$i]}" 1)"
		category="$(sh_splitarray "${AHardInfo[$i]}" 2)"
		name="$(sh_splitarray "${AHardInfo[$i]}" 3)"
		icon="$(sh_splitarray "${AHardInfo[$i]}" 4)"
		pkexec="$(sh_splitarray "${AHardInfo[$i]}" 5)"
		show="$(sh_splitarray "${AHardInfo[$i]}" 6)"
		SHOW_HARDINFO "$category_inxi" "$parameter_inxi" "$category" "$name" "$icon" "$pkexec" "$show"
	}
}

#sh_debug
sh_config
sh_remove_tmp_files
sh_set_show "$1"
sh_set_hardinfo
sh_process_hardinfo

