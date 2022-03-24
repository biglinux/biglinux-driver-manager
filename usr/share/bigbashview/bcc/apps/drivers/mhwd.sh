#!/bin/bash

# 1 $CATEGORY_INXI
# 2 $NAME
# 3 $CATEGORY
CATEGORY_INXI="$1"
NAME="$2"
ICON="$3"
CATEGORY="$4"

rm -f /tmp/hardwareinfo-mhwd.html

cat << EOF >> /tmp/hardwareinfo-mhwd.html
<div class=\"app-card more\" style=\"max-height: 100%;\"><div class=titlecard><span>"
Mhwd driver</div>"
</span><div class="app-card__subtext">'
<div class=hardwareSpaceNull>'

<div class="content">
<div class="text_area">
<textarea style="width:100%;" rows="20">

$(mhwd -li)

</textarea></div></div>
</div></div></div>
EOF






####################


cat << EOF >> /tmp/hardwareinfo-mhwd.html
<div class=\"app-card more\" style=\"max-height: 100%;\"><div class=titlecard><span>
Mhwd kernel</div>"
</span><div class="app-card__subtext">
<div class=hardwareSpaceNull>

<div class="content">
<div class="text_area">
<textarea style="width:100%;" rows="20">

$(mhwd-kernel -li)

</textarea></div></div>
</div></div></div>

EOF
