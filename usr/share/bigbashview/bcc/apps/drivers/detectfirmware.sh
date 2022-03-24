#!/bin/bash

##############
# Detect firmware needed
# By Bruno Goncalves < www.biglinux.com.br >
# 2022/03/01
# License GPL V2 or greater
###############

OIFS=$IFS
IFS=$'\n'

INSTALLED_PKGS="$(pacman -Q | cut -f1 -d" ")"




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
  DRIVER_COMPATIBLE=$""
fi

if [ "$VIDEO_DRIVER_ENABLED" = "true" ]; then
  DRIVER_ENABLE_OR_DISABLE=$"Remover"
  INSTALL_OR_REMOVE_VIDEO="remove_video_now"
  DISABLE_BUTTON="false"
else
  DRIVER_ENABLE_OR_DISABLE=$"Instalar"
  INSTALL_OR_REMOVE_VIDEO="install_video_now"
  if [ "$VIDEO_DRIVER_NVIDIA_ENABLED" = "true" ] && [ "$(echo "$VIDEO_DRIVER_NAME" | grep nvidia)" != "" ]; then
    DISABLE_BUTTON="true"
    DRIVER_ENABLE_OR_DISABLE=$"Já existe outro driver nVidia instalado, para instalar este driver, remova primeiro o driver instalado."
  else
    DISABLE_BUTTON="false"
  fi

fi
VIDEO_DRIVER_NAME_CLEAN="$(echo "$VIDEO_DRIVER_NAME" | sed 's|-| |g')"

cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"

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
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
                <div class="app-card-buttons">
                  <a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_VIDEO}=${VIDEO_DRIVER_NAME}">$DRIVER_ENABLE_OR_DISABLE</a>
                </div>
              </div>
EOF

else
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
                <div class="app-card-buttons">
                  $DRIVER_ENABLE_OR_DISABLE
                </div>
              </div>
EOF

fi
}




###################################
#
# MHWD import info OPEN, used to video drivers
#
###################################


# If module is proprietary show false
# Result example: video-nvidia-470xx false
VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE="$(mhwd -la | awk '{ print $1 " " $3 }' | grep -i video-)"

# Show compatible with this hardware
VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE="$(mhwd -l | awk '{ print $1 }' | grep -i video-)"

# Show if installed
VIDEO_DRIVER_ENABLED_LIST="$(mhwd -li | awk '{ print $1 }' | grep -i video-)"

# Show if nvidia driver is enabled
if [ "$(echo "$VIDEO_DRIVER_ENABLED_LIST" | grep -i nvidia)" != "" ]; then
    VIDEO_DRIVER_NVIDIA_ENABLED="true"
fi


for i  in  $VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE; do

    VIDEO_DRIVER_NAME="$(echo "$i" | cut -f1 -d" ")"
    VIDEO_DRIVER_OPEN="$(echo "$i" | cut -f2 -d" ")"

    if [ "$(echo "$VIDEO_DRIVER_ENABLED_LIST" | grep "^$VIDEO_DRIVER_NAME$" )" != "" ]
    then
        VIDEO_DRIVER_ENABLED="true"
    else
        VIDEO_DRIVER_ENABLED="false"
    fi

    if [ "$(echo "$VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE" | grep -ve video-linux -ve video-modesetting -ve video-vesa | grep "^$VIDEO_DRIVER_NAME$" )" != "" ]
    then
        VIDEO_DRIVER_COMPATIBLE="true"
        CATEGORY="Gpu Star"
    else
        VIDEO_DRIVER_COMPATIBLE="false"
        CATEGORY="Gpu"
    fi


# echo "Driver: $VIDEO_DRIVER_NAME"
# echo "Open: $VIDEO_DRIVER_OPEN"
# echo "Enabled: $VIDEO_DRIVER_ENABLED"
# echo "Compatible: $VIDEO_DRIVER_COMPATIBLE"

SHOW_DRIVER "$VIDEO_DRIVER_NAME" "$VIDEO_DRIVER_ENABLED" "$VIDEO_DRIVER_COMPATIBLE" "$VIDEO_DRIVER_OPEN" 

done

###################################
#
# MHWD import info CLOSE
#
###################################

SHOW_MODULE() {
# $PKG
# $MODULE
# $NAME
# $ID
# $CATEGORY
# $MODULE_COMPATIBLE
# $MODULE_LOADED
# $PKG_INSTALLED

if [ "$MODULE_COMPATIBLE" = "true" ]; then
  DRIVER_COMPATIBLE=$"Este driver parece compatível com este computador."
else
  DRIVER_COMPATIBLE=$""
fi

if [ "$PKG_INSTALLED" = "true" ]; then
  PKG_INSTALLED_OR_NOT=$"Remover"
  INSTALL_OR_REMOVE_PKG="remove_video_now"
else
  PKG_INSTALLED_OR_NOT=$"Instalar"
  INSTALL_OR_REMOVE_PKG="install_video_now"
fi


cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_module_$PKG.html"

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
                  <a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_PKG}=${PKG}">$PKG_INSTALLED_OR_NOT</a>
                </div>
              </div>

EOF


}

###################################
#
# Other modules from BigLinux Scripts, using PCI
# OPEN
#
###################################



###################################
#
# MHWD import info CLOSE
#
###################################

SHOW_MODULE() {
# $PKG
# $MODULE
# $NAME
# $ID
# $CATEGORY
# $MODULE_COMPATIBLE
# $MODULE_LOADED
# $PKG_INSTALLED

if [ "$MODULE_COMPATIBLE" = "true" ]; then
  DRIVER_COMPATIBLE=$"Este driver parece compatível com este computador."
else
  DRIVER_COMPATIBLE=$""
fi

if [ "$PKG_INSTALLED" = "true" ]; then
  PKG_INSTALLED_OR_NOT=$"Remover"
  INSTALL_OR_REMOVE_PKG="remove_video_now"
else
  PKG_INSTALLED_OR_NOT=$"Instalar"
  INSTALL_OR_REMOVE_PKG="install_video_now"
fi


cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_module_$PKG.html"

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
                  <a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_PKG}=${PKG}">$PKG_INSTALLED_OR_NOT</a>
                </div>
              </div>

EOF


}

###################################
#
# Other modules from BigLinux Scripts, using PCI
# OPEN
#
###################################



# PCI
PCI_LIST="$(grep -Ri : device-ids/ | grep 'pci.ids')"
# Result example from list
# device-ids/r8101/pci.ids:10EC:8136
PCI_IN_PC="$(lspci -nn | cut -f2- -d" ")"
PCI_LIST_MODULES="$(echo "$PCI_LIST" | cut -f2 -d/ | sort -u)"

for MODULE  in  $PCI_LIST_MODULES; do

  ID_LIST="$(echo "$PCI_LIST" | grep "/$MODULE/" | rev | cut -f1,2 -d: | rev)"
  CATEGORY="$(cat device-ids/$MODULE/category)"
  PKG="$(cat device-ids/$MODULE/pkg)"
  DESC="$(cat device-ids/$MODULE/description)"

  MODULE_COMPATIBLE="false"

  for i in  $ID_LIST; do
  
    if [ "$(echo "$PCI_IN_PC" | grep "$i")" != "" ]; then
  
      NAME="$(echo "$PCI_IN_PC" | grep "$ID" | cut -f2- -d" ")"
      MODULE_COMPATIBLE="true"
      CATEGORY="$CATEGORY Star"
    fi
  done

  if [ "$(lsmod | cut -f1 -d" " | grep "^$MODULE$")" != "" ]; then
    MODULE_LOADED="true"
  else
    MODULE_LOADED="false"
  fi

  if [ "$(echo "$INSTALLED_PKGS" | grep ^$PKG$)" != "" ]; then
    PKG_INSTALLED="true"
  else
    PKG_INSTALLED="false"
  fi


# echo "Device: $NAME"
# echo "ID: $ID"
# echo "MODULE: $MODULE"
# echo "PKG: $PKG"

  SHOW_MODULE "$PKG" "$MODULE" "$NAME" "$ID" "$CATEGORY" "$MODULE_COMPATIBLE" "$MODULE_LOADED" "$PKG_INSTALLED" "$DESC"
done



# PCI
PCI_LIST="$(grep -Ri : device-ids/ | grep 'pci.ids')"
# Result example from list
# device-ids/r8101/pci.ids:10EC:8136
PCI_IN_PC="$(lspci -nn | cut -f2- -d" ")"
PCI_LIST_MODULES="$(echo "$PCI_LIST" | cut -f2 -d/ | sort -u)"

for MODULE  in  $PCI_LIST_MODULES; do

  ID_LIST="$(echo "$PCI_LIST" | grep "/$MODULE/" | rev | cut -f1,2 -d: | rev)"
  CATEGORY="$(cat device-ids/$MODULE/category)"
  PKG="$(cat device-ids/$MODULE/pkg)"
  DESC="$(cat device-ids/$MODULE/description)"

  MODULE_COMPATIBLE="false"

  for i in  $ID_LIST; do
  
    if [ "$(echo "$PCI_IN_PC" | grep "$i")" != "" ]; then
  
      NAME="$(echo "$PCI_IN_PC" | grep "$ID" | cut -f2- -d" ")"
      MODULE_COMPATIBLE="true"
      CATEGORY="$CATEGORY Star"
    fi
  done

  if [ "$(lsmod | cut -f1 -d" " | grep "^$MODULE$")" != "" ]; then
    MODULE_LOADED="true"
  else
    MODULE_LOADED="false"
  fi

  if [ "$(echo "$INSTALLED_PKGS" | grep ^$PKG$)" != "" ]; then
    PKG_INSTALLED="true"
  else
    PKG_INSTALLED="false"
  fi


# echo "Device: $NAME"
# echo "ID: $ID"
# echo "MODULE: $MODULE"
# echo "PKG: $PKG"

  SHOW_MODULE "$PKG" "$MODULE" "$NAME" "$ID" "$CATEGORY" "$MODULE_COMPATIBLE" "$MODULE_LOADED" "$PKG_INSTALLED" "$DESC"
done












IFS=$OIFS
