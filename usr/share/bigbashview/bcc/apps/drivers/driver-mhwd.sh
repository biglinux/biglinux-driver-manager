#!/bin/bash


##################################
#  Author1: Bruno Goncalves (www.biglinux.com.br) 
#  Author2: Rafael Ruscher (rruscher@gmail.com)  
#  Date:    2022/02/28 
#  
#  Description: Control Center to help usage of BigLinux 
#  
# Licensed by GPL V2 or greater
##################################

#Translation
export TEXTDOMAINDIR="/usr/share/locale"
export TEXTDOMAIN=biglinux-driver-manager

OIFS=$IFS
IFS=$'\n'

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
  DRIVER_COMPATIBLE=$""
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
    DISABLED_MESSAGE="Antes de instalar este driver, remova o outro driver Nvidia."
    #DRIVER_ENABLE_OR_DISABLE=$"Já existe outro driver nVidia instalado, para instalar este driver, remova primeiro o driver instalado."
  else
    INSTALL_OR_REMOVE_VIDEO="install_video_now"
    DISABLED_BUTTON=""
    DISABLED_MESSAGE=""
  fi

fi
VIDEO_DRIVER_NAME_CLEAN="$(echo "$VIDEO_DRIVER_NAME" | sed 's|-| |g')"

    if [ "$VIDEO_DRIVER_NAME_CLEAN" = "video nvidia"  ]; then
        VIDEO_DRIVER_NAME_CLEAN="video nvidia $(LANG=C pacman -Si nvidia-utils | grep "^Version" | cut -f2 -d":" | sed 's|\..*|xx|g')"
        
    fi

cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"

              <div class="app-card $CATEGORY">
                <span class="icon-cat icon-category-$CATEGORY" style="display:table-cell;"></span><span class="titlespan" style="display:table-cell;">
                  $VIDEO_DRIVER_NAME_CLEAN
                </span>
                <div class="app-card__subtext">
                  $OPEN_OR_PROPRIETARY
                  <br><br>
                  $DESC
                  $DISABLED_MESSAGE
                  </div>
EOF


cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_video_$VIDEO_DRIVER_NAME.html"
                <div class="app-card-buttons">
                <a class="content-button status-button  $DISABLED_BUTTON" $DISABLED_BUTTON" onclick="disableBodyConfig();" href="index.sh.htm?${INSTALL_OR_REMOVE_VIDEO}=${VIDEO_DRIVER_NAME}">
                  $DRIVER_ENABLE_OR_DISABLE
                </a>
              </div>
              </div>
EOF

}




###################################
#
# MHWD import info OPEN, used to video drivers
#
###################################


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
        if [ "$(echo "$VIDEO_DRIVER_NAME" | grep network)" != ""  ]; then
          CATEGORY="wifi Star"

          if [ "$(echo "$VIDEO_DRIVER_NAME" | grep 8168)" != ""  ]; then
              CATEGORY="ethernet Star"
          fi
        else
          CATEGORY="Gpu Star"
        fi
    else
        VIDEO_DRIVER_COMPATIBLE="false"
        if [ "$(echo "$VIDEO_DRIVER_NAME" | grep network)" != ""  ]; then
          CATEGORY="wifi"
          if [ "$(echo "$VIDEO_DRIVER_NAME" | grep 8168)" != ""  ]; then
              CATEGORY="ethernet"
          fi
        else
          CATEGORY="Gpu"
        fi

    fi


# echo "Driver: $VIDEO_DRIVER_NAME"
# echo "Open: $VIDEO_DRIVER_OPEN"
# echo "Enabled: $VIDEO_DRIVER_ENABLED"
# echo "Compatible: $VIDEO_DRIVER_COMPATIBLE"

SHOW_DRIVER "$VIDEO_DRIVER_NAME" "$VIDEO_DRIVER_ENABLED" "$VIDEO_DRIVER_COMPATIBLE" "$VIDEO_DRIVER_OPEN"

done



IFS=$OIFS

