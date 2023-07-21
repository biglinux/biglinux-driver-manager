#!/usr/bin/env bash


if [[ "$ACTION" = "install_pkg_pamac" ]]; then
	if pacman -Si $DRIVER; then
		pamac-installer $DRIVER &
	else
		pamac-installer --build $DRIVER &
	fi
fi

if [[ "$ACTION" = "remove_pkg_pamac" ]]; then
	pamac-installer --remove $DRIVER &
fi

PID="$!"
[[ -z "$PID" ]] && exit

:<<comment
CONTADOR=0
while [[ $CONTADOR -lt 100 ]]; do
	if [[ "$(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ")" != "" ]]; then
		xsetprop -id=$(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") --atom WM_TRANSIENT_FOR --value $(wmctrl -p -l -x | grep Big-Driver-Manager$ | cut -f1 -d" ") -f 32x
		wmctrl -i -r $(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") -b add,skip_pager,skip_taskbar
		wmctrl -i -r $(wmctrl -p -l | grep -m1 " $PID " | cut -f1 -d" ") -b toggle,modal
		break
	fi
	sleep 0.1
	((++CONTADOR))
done
wait
comment

# Função para obter o ID da janela pelo PID
get_window_id() {
	wmctrl -lp | awk -v pid="$1" '$3 == pid {print $1; exit}'
}

# Aguardar até encontrar a janela com o PID específico
while [[ -z $(get_window_id "$PID") ]]; do
	sleep 0.1
done

# Obter o ID da janela
WINDOW_ID=$(get_window_id "$PID")

# Definir a janela como transitória para outra janela com o nome "Big-Driver-Manager"
xprop -id "$WINDOW_ID" -f WM_TRANSIENT_FOR 32a -set WM_TRANSIENT_FOR "$(get_window_id "Big-Driver-Manager")"

# Definir propriedades da janela
wmctrl -ir "$WINDOW_ID" -b add,skip_pager,skip_taskbar
wmctrl -ir "$WINDOW_ID" -b toggle,modal
wait
