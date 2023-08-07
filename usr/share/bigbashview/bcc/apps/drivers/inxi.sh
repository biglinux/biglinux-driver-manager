#!/usr/bin/env bash
#shellcheck disable=SC2155
#shellcheck source=/dev/null

#  inxi.sh
#  Created: 0000/00/00
#  Altered: 2023/08/07
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

APP="${0##*/}"
_VERSION_="1.0.0-20230807"
BOOTLOG="/tmp/bigcontrolcenter-$USER-$(date +"%d%m%Y").log"
LOGGER='/dev/tty8'
LIBRARY=${LIBRARY:-'/usr/share/bigbashview/bcc/shell'}
[[ -f "${LIBRARY}/bcclib.sh" ]] && source "${LIBRARY}/bcclib.sh"

function sh_config {
	#Translation
	export TEXTDOMAINDIR="/usr/share/locale"
	export TEXTDOMAIN=biglinux-driver-manager
	declare -g DEVICE_INFO=$"Ver informações do dispositivo no Linux Hardware"
	declare -g PCI_IDS
	declare -g USB_IDS
	declare -gA AHardInfo
	declare -ga a
	declare -i lshow=0
}

function sh_get_ids {
	PCI_IDS="$(lspci -n | awk '{print $3}')"
	USB_IDS="$(lsusb | awk '{print $6}')"
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

	# Início do bloco HTML
	{
		echo "<div class=\"app-card $category\" style=\"max-height: 100%;\">"
		echo '<div class="app-card__title">'
		echo $name
		echo '</div>'
		echo '<div class="app-card__subtext">'
	} >>"$cfile"

	# Comando inxi e formatação HTML
	parameter_inxi=$(sh_get_parameters)
	$pkexec inxi "$parameter_inxi" "-c2" "--$category_inxi" -y 100 --indents 5 |   # Executa o comando 'inxi' com alguns parâmetros
		iconv -t UTF-8 2>- |                                                        # Converte a saída para codificação UTF-8
		grep '     ' |                                                              # Filtra as linhas que contêm seis espaços (delimitador/formato)
		sed 's|          ||g' |                                                     # Remove os seis espaços iniciais de cada linha
		tr '\n ' ' ' |                                                              # Substitui as quebras de linha por espaços (unifica em uma linha)
		sed 's|      |\n     |g' |                                                  # Insere quebras de linha antes de sequências de seis espaços (volta ao formato multi-linha)
		ansi2html -f 18px -l |                                                      # Converte escape sequences ANSI para HTML com fonte de tamanho 18px e cor
		sed 's|           <span class="|<span class="subcategory1 |g' |             # Adiciona a classe "subcategory1" para estilizar os elementos HTML
		grep -A 9999 '<pre class="ansi2html-content">' |                            # Extrai linhas contendo '<pre class="ansi2html-content">' e as próximas 9999 linhas
		grep -v '</html>' | grep -v '</body>' |                                     # Remove linhas contendo '</html>' e '</body>'
		sed 's|<pre class="ansi2html-content">||g; s|</pre>||g; s|<span class="ansi1 ansi34">|<br><span class="ansi1 ansi34">|g; s|     |</div><div class=hardwareSpace>|g; s|</div><br><span class="ansi1 ansi34">|</div><span class="hardwareTitle2">|g;
	s|<span class="ansi1 ansi34">System Temperatures:|<span class="ansi1 ansi33">System Temperatures|g;
	s|<span class="ansi1 ansi34">Fan Speeds (RPM):|<span class="ansi1 ansi33">Fan Speeds (RPM)|g;
	s|<span class="ansi1 ansi34">Local Storage:|<span class="ansi1 ansi33">Local Storage|g;
	s|<span class="ansi1 ansi34">RAM:|<span class="ansi1 ansi33">RAM|g;
	s|<span class="ansi1 ansi34">Info:|<span class="ansi1 ansi33">Info|g;
	s|<span class="ansi1 ansi34">Topology:|<span class="ansi1 ansi33">Topology|g;
	s|<span class="ansi1 ansi34">Speed (MHz):|<span class="ansi1 ansi33">Speed (MHz)|g' >>"$cfile"

	# Fim do bloco HTML
	echo '</div></div>' >>"$cfile"

	# Manipulação de botões relacionados a dispositivos PCI e USB
	# Loop otimizado usando 'grep', 'sed', 'rev' e 'cut'
	# Para cada valor 'i' extraído de 'Chip-ID' em "$cfile":

	# Procura linhas contendo "Chip-ID" (ignorando diferenças de maiúsculas e minúsculas) no arquivo especificado por "$cfile"
	# Remove todo o texto após o trecho "<br><span class="ansi1 ansi34">class-ID" nas linhas selecionadas pelo 'grep'
	# Inverte cada linha para facilitar a extração da primeira coluna
	# Extrai a primeira coluna (delimitada por espaços) de cada linha após a inversão
	# Inverte novamente cada linha para restaurar a ordem original
	# Ordena os valores extraídos em ordem alfabética e remove quaisquer linhas duplicadas, deixando apenas os valores únicos

	sh_get_ids
	for i in $(grep -i Chip-ID "$cfile" | sed 's| <br><span class="ansi1 ansi34">class-ID.*||g' | rev | cut -f1 -d" " | rev | sort -u); do
		if grep -q "$i" <<< "$PCI_IDS"; then
			format_id="${i//:/-}"
			sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run pci:$format_id')\">$DEVICE_INFO</a></div>|g" "$cfile"
		elif grep -q "$i" <<< "$USB_IDS"; then
			format_id="${i//:/-}"
			sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run usb:$format_id')\">$DEVICE_INFO</a></div>|g" "$cfile"
		fi
	done
}

function sh_get_parameters {
	if ((lshow)); then
		echo '-axx'
	else
		echo '-xz'
	fi
}

function sh_process_hardinfo {
	#Clean CPU
	if test -e '/tmp/hardwareinfo-inxi-cpu.html'; then
		grep -E -v 'Vulnerabilities:|Type:' /tmp/hardwareinfo-inxi-cpu.html >/tmp/hardwareinfo-inxi-cpu2.html
		mv -f /tmp/hardwareinfo-inxi-cpu2.html /tmp/hardwareinfo-inxi-cpu.html
	fi

	# Save dmesg
	dmesg -t --level=alert,crit,err,warn >/tmp/hardwareinfo-dmesg.html
	SHOW_HARDINFO & # the first call shows the messed up information, then it is blank to show nothing
	SHOW_HARDINFO "cpu"              "cpu"       $"Processador"                   "cpu" &
	SHOW_HARDINFO "machine"          "machine"   $"Placa mãe"                     "machine" &
	SHOW_HARDINFO "memory"           "memory"    $"Memória"                       "memory" &
	SHOW_HARDINFO "swap"             "memory"    $"Swap Memória Virtual"          "swap" &
	SHOW_HARDINFO "graphics"         "gpu"       $"Placa de vídeo"                "graphics" "pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY" &
	SHOW_HARDINFO "audio"            "audio"     $"Áudio"                         "audio" &
	SHOW_HARDINFO "network-advanced" "Network"   $"Rede"                          "network" &
	SHOW_HARDINFO "ip"               "network"   $"Conexões de Rede"              "ip" &
	SHOW_HARDINFO "usb"              "usb"       $"Dispositivos e conexões USB"   "usb" &
	SHOW_HARDINFO "slots"            "pci"       $"Portas PCI"                    "usb" &
	SHOW_HARDINFO "battery"          "battery"   $"Bateria"                       "battery" &
	SHOW_HARDINFO "disk-full"        "disk"      $"Dispositivos de Armazenamento" "disk" &
	SHOW_HARDINFO "partitions-full"  "disk"      $"Partições montadas"            "disk" &
	SHOW_HARDINFO "unmounted"        "disk"      $"Partições desmontadas"         "disk" "pkexec -u $BIGUSER" &
	SHOW_HARDINFO "logical"          "disk"      $"Dispositivos lógicos"          "disk" &
	SHOW_HARDINFO "raid"             "disk"      $"Raid"                          "disk" &
	SHOW_HARDINFO "system"           "system"    $"Sistema"                       "disk" &
	SHOW_HARDINFO "info"             "system"    $"Informações de Sistema"        "disk" &
	SHOW_HARDINFO "repos"            "system"    $"Repositórios"                  "disk" &
	SHOW_HARDINFO "bluetooth"        "bluetooth" $"Bluetooth"                     "disk" &
	SHOW_HARDINFO "sensors"          "sensors"   $"Temperatura"                   "disk" "pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY" &
	wait
}

#sh_debug
sh_config
sh_remove_tmp_files
sh_set_show "$1"
sh_process_hardinfo
