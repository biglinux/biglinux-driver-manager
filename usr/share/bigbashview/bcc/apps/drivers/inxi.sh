#!/usr/bin/env bash
#shellcheck disable=SC2155,SC2034
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

function sh_set_show {
	[[ "$1" = "show" ]] && lshow=1
}

function sh_remove_tmp_files {
	rm -f /tmp/hardwareinfo-inxi-*.html >/dev/null 2>&-
	rm -f /tmp/hardwareinfo-dmesg.html >/dev/null 2>&-
}

function SHOW_HARDINFO {
	local category_inxi="$1"
	local category="$2"
	local name="$3"
	local icon="$4"
	local pkexec="$5"
	local cfile="/tmp/hardwareinfo-inxi-$category_inxi.html"
	local parameter_inxi

{
	echo "<div class=\"app-card $category\" style=\"max-height: 100%;\">"
	echo "<div class=\"app-card__title\">"
	echo $name
	echo "</div>"
	echo '<div class="app-card__subtext">'
} >>"$cfile"


	parameter_inxi=$(sh_get_parameters)
	$pkexec inxi "$parameter_inxi" "--color" "--$category_inxi" -y 100 --indents 5 \
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
			sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run pci:$(echo "$i" | sed 's|:|-|g')')\">$DEVICE_INFO</a></div>|g" "$cfile"
		elif [ "$(echo "$USB_IDS" | grep "$i")" != "" ]; then
			sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run usb:$(echo "$i" | sed 's|:|-|g')')\">$DEVICE_INFO</a></div>|g" "$cfile"
		fi
	done
}

function sh_get_parameters {
	if (( lshow )); then
		echo '-axx'
	else
		echo '-xz'
	fi
}

function sh_set_hardinfo {
	#Clean CPU
	if test -e '/tmp/hardwareinfo-inxi-cpu.html'; then
		grep -ve 'Vulnerabilities:' -ve 'Type:' /tmp/hardwareinfo-inxi-cpu.html >/tmp/hardwareinfo-inxi-cpu2.html
		mv -f /tmp/hardwareinfo-inxi-cpu2.html /tmp/hardwareinfo-inxi-cpu.html
	fi

	# Save dmesg
	dmesg -t --level=alert,crit,err,warn >/tmp/hardwareinfo-dmesg.html

	# Inicializar o array "a" com os dados em linhas separadas, com um $ na frente de cada string
	a=($"Processador"
	   $"Placa mãe"
	   $"Memória"
	   $"Swap Memória Virtual"
	   $"Placa de vídeo"
	   $"Áudio"
	   $"Rede"
	   $"Conexões de Rede"
	   $"Dispositivos e conexões USB"
	   $"Portas PCI"
	   $"Bateria"
	   $"Dispositivos de Armazenamento"
	   $"Partições montadas"
	   $"Partições desmontadas"
	   $"Dispositivos lógicos"
	   $"Raid"
	   $"Sistema"
	   $"Informações de Sistema"
	   $"Repositórios"
	   $"Bluetooth"
	   $"Temperatura"
	)

	# Inicializar o array associativo "AHardInfo" com os dados do array "a"
	AHardInfo+=(['cpu']="cpu|${a[0]}|cpu|")
	AHardInfo+=(['machine']="machine|${a[1]}|machine|")
	AHardInfo+=(['memory']="memory|${a[2]}|memory|")
	AHardInfo+=(['swap']="memory|${a[3]}|swap|")
	AHardInfo+=(['graphics']="gpu|${a[4]}|graphics|pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY")
	AHardInfo+=(['audio']="audio|${a[5]}|audio|")
	AHardInfo+=(['network-advanced']="Network|${a[6]}|network|")
	AHardInfo+=(['ip']="network|${a[7]}|ip|")
	AHardInfo+=(['usb']="usb|${a[8]}|usb|")
	AHardInfo+=(['slots']="pci|${a[9]}|usb|")
	AHardInfo+=(['battery']="battery|${a[10]}|battery|")
	AHardInfo+=(['disk-full']="disk|${a[11]}|disk|")
	AHardInfo+=(['partitions-full']="disk|${a[12]}|disk|")
	AHardInfo+=(['unmounted']="disk|${a[13]}|disk|pkexec -u $BIGUSER")
	AHardInfo+=(['logical']="disk|${a[14]}|disk|")
	AHardInfo+=(['raid']="disk|${a[15]}|disk|")
	AHardInfo+=(['system']="system|${a[16]}|disk|")
	AHardInfo+=(['info']="system|${a[17]}|disk|")
	AHardInfo+=(['repos']="system|${a[18]}|disk|")
	AHardInfo+=(['bluetooth']="bluetooth|${a[19]}|disk|")
	AHardInfo+=(['sensors']="sensors|${a[20]}|disk|pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY")
}

function sh_process_hardinfo {
	local category_inxi
	local parameter_inxi
	local category
	local name
	local icon
	local pkexec

	for i in "${!AHardInfo[@]}"; {
		category_inxi="$i"
		category="$(sh_splitarray "${AHardInfo[$i]}" 1)"
		name="$(sh_splitarray "${AHardInfo[$i]}" 2)"
		icon="$(sh_splitarray "${AHardInfo[$i]}" 3)"
		pkexec="$(sh_splitarray "${AHardInfo[$i]}" 4)"
		SHOW_HARDINFO "$category_inxi" "$category" "$name" "$icon" "$pkexec"
	}
}

#sh_debug
sh_config
sh_remove_tmp_files
sh_set_show "$1"
sh_set_hardinfo
sh_process_hardinfo

