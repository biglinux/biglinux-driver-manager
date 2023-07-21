#!/usr/bin/env bash

function sh_config {
	# 1 $CATEGORY_INXI
	# 2 $NAME
	# 3 $CATEGORY
	declare -g CATEGORY_INXI="$1"
	declare -g NAME="$2"
	declare -g ICON="$3"
	declare -g CATEGORY="$4"
	declare -g hardinfo_file='/tmp/hardwareinfo-mhwd.html'
}

function sh_remove_hardinfo_file {
	[[ -e "$hardinfo_file" ]] && rm -f "$hardinfo_file"
}

function sh_mhwd_html {
	local ctitle="$1"
	local cjob="$2"

	{
		echo '<div class=app-card more style=max-height: 100%;>'
		echo '<div class=titlecard><span>'
		echo "$ctitle"
		echo '</div></span>'
		echo '<div class="app-card__subtext">'
		echo '<div class=hardwareSpaceNull>'
		echo '<div class="content">'
		echo '<div class="text_area">'
		echo '<textarea style="width:100%;" rows="20">'
		eval "$cjob"
		echo '</textarea></div></div></div></div></div>'
	} >> "$hardinfo_file"
}

sh_config "$@"
sh_remove_hardinfo_file
sh_mhwd_html 'Mhwd driver' "mhwd -li"
sh_mhwd_html 'Mhwd kernel' "mhwd-kernel -li"
