#!/bin/bash
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
##############
dd-desc.sh
dd-desc.sh
dd-desc.sh
# Detect firmware needed
dd-desc.sh
dd-desc.sh
dd-desc.sh
# By Bruno Goncalves < www.biglinux.com.br >
dd-desc.sh
dd-desc.sh
dd-desc.sh
# 2022/03/01
dd-desc.sh
dd-desc.sh
dd-desc.sh
# License GPL V2 or greater
dd-desc.sh
dd-desc.sh
dd-desc.sh
###############
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
OIFS=$IFS
dd-desc.sh
dd-desc.sh
dd-desc.sh
IFS=$'\n'
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
INSTALLED_PKGS="$(pacman -Q | cut -f1 -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
SHOW_DRIVER() {
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $CATEGORY
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $VIDEO_DRIVER_NAME
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $VIDEO_DRIVER_ENABLED
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $VIDEO_DRIVER_COMPATIBLE
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $VIDEO_DRIVER_OPEN
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$VIDEO_DRIVER_OPEN" = "true" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  OPEN_OR_PROPRIETARY=$"Este driver é software livre."
dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
  OPEN_OR_PROPRIETARY=$"Este driver é proprietário."
dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$VIDEO_DRIVER_COMPATIBLE" = "true" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_COMPATIBLE=$"Este driver parece compatível com este computador."
dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_COMPATIBLE=$""
dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$VIDEO_DRIVER_ENABLED" = "true" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_ENABLE_OR_DISABLE=$"Remover"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  INSTALL_OR_REMOVE_VIDEO="remove_video_now"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DISABLE_BUTTON="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_ENABLE_OR_DISABLE=$"Instalar"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  INSTALL_OR_REMOVE_VIDEO="install_video_now"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  if [ "$VIDEO_DRIVER_NVIDIA_ENABLED" = "true" ] && [ "$(echo "$VIDEO_DRIVER_NAME" | grep nvidia)" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
    DISABLE_BUTTON="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    DRIVER_ENABLE_OR_DISABLE=$"Já existe outro driver nVidia instalado, para instalar este driver, remova primeiro o driver instalado."
dd-desc.sh
dd-desc.sh
dd-desc.sh
  else
dd-desc.sh
dd-desc.sh
dd-desc.sh
    DISABLE_BUTTON="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh
VIDEO_DRIVER_NAME_CLEAN="$(echo "$VIDEO_DRIVER_NAME" | sed 's|-| |g')"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
              <div class="app-card $CATEGORY">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <span>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $VIDEO_DRIVER_NAME_CLEAN
dd-desc.sh
dd-desc.sh
dd-desc.sh
                </span>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <div class="app-card__subtext">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $OPEN_OR_PROPRIETARY
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  <br><br>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $DESC
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $DRIVER_COMPATIBLE
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
EOF
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$DISABLE_BUTTON" = "false" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <div class="app-card-buttons">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  <a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_VIDEO}=${VIDEO_DRIVER_NAME}">$DRIVER_ENABLE_OR_DISABLE</a>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
              </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
EOF
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <div class="app-card-buttons">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $DRIVER_ENABLE_OR_DISABLE
dd-desc.sh
dd-desc.sh
dd-desc.sh
                </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
              </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
EOF
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh
}
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
# MHWD import info OPEN, used to video drivers
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# If module is proprietary show false
dd-desc.sh
dd-desc.sh
dd-desc.sh
# Result example: video-nvidia-470xx false
dd-desc.sh
dd-desc.sh
dd-desc.sh
VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE="$(mhwd -la | awk '{ print $1 " " $3 }' | grep -i video-)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# Show compatible with this hardware
dd-desc.sh
dd-desc.sh
dd-desc.sh
VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE="$(mhwd -l | awk '{ print $1 }' | grep -i video-)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# Show if installed
dd-desc.sh
dd-desc.sh
dd-desc.sh
VIDEO_DRIVER_ENABLED_LIST="$(mhwd -li | awk '{ print $1 }' | grep -i video-)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# Show if nvidia driver is enabled
dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$(echo "$VIDEO_DRIVER_ENABLED_LIST" | grep -i nvidia)" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
    VIDEO_DRIVER_NVIDIA_ENABLED="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
for i  in  $VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE; do
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    VIDEO_DRIVER_NAME="$(echo "$i" | cut -f1 -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    VIDEO_DRIVER_OPEN="$(echo "$i" | cut -f2 -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    if [ "$(echo "$VIDEO_DRIVER_ENABLED_LIST" | grep "^$VIDEO_DRIVER_NAME$" )" != "" ]
dd-desc.sh
dd-desc.sh
dd-desc.sh
    then
dd-desc.sh
dd-desc.sh
dd-desc.sh
        VIDEO_DRIVER_ENABLED="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    else
dd-desc.sh
dd-desc.sh
dd-desc.sh
        VIDEO_DRIVER_ENABLED="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
    if [ "$(echo "$VIDEO_DRIVER_COMPATIBLE_WITH_THIS_HARDWARE" | grep -ve video-linux -ve video-modesetting -ve video-vesa | grep "^$VIDEO_DRIVER_NAME$" )" != "" ]
dd-desc.sh
dd-desc.sh
dd-desc.sh
    then
dd-desc.sh
dd-desc.sh
dd-desc.sh
        VIDEO_DRIVER_COMPATIBLE="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
        CATEGORY="Gpu Star"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    else
dd-desc.sh
dd-desc.sh
dd-desc.sh
        VIDEO_DRIVER_COMPATIBLE="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
        CATEGORY="Gpu"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "Driver: $VIDEO_DRIVER_NAME"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "Open: $VIDEO_DRIVER_OPEN"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "Enabled: $VIDEO_DRIVER_ENABLED"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "Compatible: $VIDEO_DRIVER_COMPATIBLE"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
SHOW_DRIVER "$VIDEO_DRIVER_NAME" "$VIDEO_DRIVER_ENABLED" "$VIDEO_DRIVER_COMPATIBLE" "$VIDEO_DRIVER_OPEN" 
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
done
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
# MHWD import info CLOSE
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
SHOW_MODULE() {
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $PKG
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $MODULE
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $NAME
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $ID
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $CATEGORY
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $MODULE_COMPATIBLE
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $MODULE_LOADED
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $PKG_INSTALLED
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$MODULE_COMPATIBLE" = "true" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_COMPATIBLE=$"Este driver parece compatível com este computador."
dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_COMPATIBLE=$""
dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$PKG_INSTALLED" = "true" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  PKG_INSTALLED_OR_NOT=$"Remover"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  INSTALL_OR_REMOVE_PKG="remove_video_now"
dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
  PKG_INSTALLED_OR_NOT=$"Instalar"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  INSTALL_OR_REMOVE_PKG="install_video_now"
dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_module_$PKG.html"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
              <div class="app-card $CATEGORY">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <span><svg viewBox="0 0 512 512">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                    <path fill="currentColor" d="M204.3 5C104.9 24.4 24.8 104.3 5.2 203.4c-37 187 131.7 326.4 258.8 306.7 41.2-6.4 61.4-54.6 42.5-91.7-23.1-45.4 9.9-98.4 60.9-98.4h79.7c35.8 0 64.8-29.6 64.9-65.3C511.5 97.1 368.1-26.9 204.3 5zM96 320c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm32-128c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm128-64c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm128 64c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32z" />
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  </svg>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $MODULE
dd-desc.sh
dd-desc.sh
dd-desc.sh
                </span>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <div class="app-card__subtext">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $DESC
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $DRIVER_COMPATIBLE
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <div class="app-card-buttons">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  <a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_PKG}=${PKG}">$PKG_INSTALLED_OR_NOT</a>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
              </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
EOF
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
}
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
# Other modules from BigLinux Scripts, using PCI
dd-desc.sh
dd-desc.sh
dd-desc.sh
# OPEN
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
# MHWD import info CLOSE
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
SHOW_MODULE() {
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $PKG
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $MODULE
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $NAME
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $ID
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $CATEGORY
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $MODULE_COMPATIBLE
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $MODULE_LOADED
dd-desc.sh
dd-desc.sh
dd-desc.sh
# $PKG_INSTALLED
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$MODULE_COMPATIBLE" = "true" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_COMPATIBLE=$"Este driver parece compatível com este computador."
dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DRIVER_COMPATIBLE=$""
dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
if [ "$PKG_INSTALLED" = "true" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  PKG_INSTALLED_OR_NOT=$"Remover"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  INSTALL_OR_REMOVE_PKG="remove_video_now"
dd-desc.sh
dd-desc.sh
dd-desc.sh
else
dd-desc.sh
dd-desc.sh
dd-desc.sh
  PKG_INSTALLED_OR_NOT=$"Instalar"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  INSTALL_OR_REMOVE_PKG="install_video_now"
dd-desc.sh
dd-desc.sh
dd-desc.sh
fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_module_$PKG.html"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
              <div class="app-card $CATEGORY">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <span><svg viewBox="0 0 512 512">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                    <path fill="currentColor" d="M204.3 5C104.9 24.4 24.8 104.3 5.2 203.4c-37 187 131.7 326.4 258.8 306.7 41.2-6.4 61.4-54.6 42.5-91.7-23.1-45.4 9.9-98.4 60.9-98.4h79.7c35.8 0 64.8-29.6 64.9-65.3C511.5 97.1 368.1-26.9 204.3 5zM96 320c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm32-128c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm128-64c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32zm128 64c-17.7 0-32-14.3-32-32s14.3-32 32-32 32 14.3 32 32-14.3 32-32 32z" />
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  </svg>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $MODULE
dd-desc.sh
dd-desc.sh
dd-desc.sh
                </span>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <div class="app-card__subtext">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $DESC
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  $DRIVER_COMPATIBLE
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                <div class="app-card-buttons">
dd-desc.sh
dd-desc.sh
dd-desc.sh
                  <a class="content-button status-button" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_PKG}=${PKG}">$PKG_INSTALLED_OR_NOT</a>
dd-desc.sh
dd-desc.sh
dd-desc.sh
                </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh
              </div>
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
EOF
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
}
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
# Other modules from BigLinux Scripts, using PCI
dd-desc.sh
dd-desc.sh
dd-desc.sh
# OPEN
dd-desc.sh
dd-desc.sh
dd-desc.sh
#
dd-desc.sh
dd-desc.sh
dd-desc.sh
###################################
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# PCI
dd-desc.sh
dd-desc.sh
dd-desc.sh
PCI_LIST="$(grep -Ri : device-ids/ | grep 'pci.ids')"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# Result example from list
dd-desc.sh
dd-desc.sh
dd-desc.sh
# device-ids/r8101/pci.ids:10EC:8136
dd-desc.sh
dd-desc.sh
dd-desc.sh
PCI_IN_PC="$(lspci -nn | cut -f2- -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh
PCI_LIST_MODULES="$(echo "$PCI_LIST" | cut -f2 -d/ | sort -u)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
for MODULE  in  $PCI_LIST_MODULES; do
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  ID_LIST="$(echo "$PCI_LIST" | grep "/$MODULE/" | rev | cut -f1,2 -d: | rev)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  CATEGORY="$(cat device-ids/$MODULE/category)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  PKG="$(cat device-ids/$MODULE/pkg)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DESC="$(cat device-ids/$MODULE/description)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  MODULE_COMPATIBLE="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  for i in  $ID_LIST; do
dd-desc.sh
dd-desc.sh
dd-desc.sh
  
dd-desc.sh
dd-desc.sh
dd-desc.sh
    if [ "$(echo "$PCI_IN_PC" | grep "$i")" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  
dd-desc.sh
dd-desc.sh
dd-desc.sh
      NAME="$(echo "$PCI_IN_PC" | grep "$ID" | cut -f2- -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh
      MODULE_COMPATIBLE="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
      CATEGORY="$CATEGORY Star"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    fi
dd-desc.sh
dd-desc.sh
dd-desc.sh
  done
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  if [ "$(lsmod | cut -f1 -d" " | grep "^$MODULE$")" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
    MODULE_LOADED="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  else
dd-desc.sh
dd-desc.sh
dd-desc.sh
    MODULE_LOADED="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  if [ "$(echo "$INSTALLED_PKGS" | grep ^$PKG$)" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
    PKG_INSTALLED="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  else
dd-desc.sh
dd-desc.sh
dd-desc.sh
    PKG_INSTALLED="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "Device: $NAME"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "ID: $ID"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "MODULE: $MODULE"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "PKG: $PKG"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  SHOW_MODULE "$PKG" "$MODULE" "$NAME" "$ID" "$CATEGORY" "$MODULE_COMPATIBLE" "$MODULE_LOADED" "$PKG_INSTALLED" "$DESC"
dd-desc.sh
dd-desc.sh
dd-desc.sh
done
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# PCI
dd-desc.sh
dd-desc.sh
dd-desc.sh
PCI_LIST="$(grep -Ri : device-ids/ | grep 'pci.ids')"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# Result example from list
dd-desc.sh
dd-desc.sh
dd-desc.sh
# device-ids/r8101/pci.ids:10EC:8136
dd-desc.sh
dd-desc.sh
dd-desc.sh
PCI_IN_PC="$(lspci -nn | cut -f2- -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh
PCI_LIST_MODULES="$(echo "$PCI_LIST" | cut -f2 -d/ | sort -u)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
for MODULE  in  $PCI_LIST_MODULES; do
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  ID_LIST="$(echo "$PCI_LIST" | grep "/$MODULE/" | rev | cut -f1,2 -d: | rev)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  CATEGORY="$(cat device-ids/$MODULE/category)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  PKG="$(cat device-ids/$MODULE/pkg)"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  DESC="$(cat device-ids/$MODULE/description)"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  MODULE_COMPATIBLE="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  for i in  $ID_LIST; do
dd-desc.sh
dd-desc.sh
dd-desc.sh
  
dd-desc.sh
dd-desc.sh
dd-desc.sh
    if [ "$(echo "$PCI_IN_PC" | grep "$i")" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
  
dd-desc.sh
dd-desc.sh
dd-desc.sh
      NAME="$(echo "$PCI_IN_PC" | grep "$ID" | cut -f2- -d" ")"
dd-desc.sh
dd-desc.sh
dd-desc.sh
      MODULE_COMPATIBLE="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
      CATEGORY="$CATEGORY Star"
dd-desc.sh
dd-desc.sh
dd-desc.sh
    fi
dd-desc.sh
dd-desc.sh
dd-desc.sh
  done
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  if [ "$(lsmod | cut -f1 -d" " | grep "^$MODULE$")" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
    MODULE_LOADED="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  else
dd-desc.sh
dd-desc.sh
dd-desc.sh
    MODULE_LOADED="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  if [ "$(echo "$INSTALLED_PKGS" | grep ^$PKG$)" != "" ]; then
dd-desc.sh
dd-desc.sh
dd-desc.sh
    PKG_INSTALLED="true"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  else
dd-desc.sh
dd-desc.sh
dd-desc.sh
    PKG_INSTALLED="false"
dd-desc.sh
dd-desc.sh
dd-desc.sh
  fi
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "Device: $NAME"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "ID: $ID"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "MODULE: $MODULE"
dd-desc.sh
dd-desc.sh
dd-desc.sh
# echo "PKG: $PKG"
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
  SHOW_MODULE "$PKG" "$MODULE" "$NAME" "$ID" "$CATEGORY" "$MODULE_COMPATIBLE" "$MODULE_LOADED" "$PKG_INSTALLED" "$DESC"
dd-desc.sh
dd-desc.sh
dd-desc.sh
done
dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh

dd-desc.sh
dd-desc.sh
dd-desc.sh
IFS=$OIFS
dd-desc.sh
dd-desc.sh
dd-desc.sh
