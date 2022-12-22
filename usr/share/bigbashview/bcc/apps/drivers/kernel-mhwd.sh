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
# kernel current version like mhwd
IFS=. read -r major minor _ <<< "$(uname -r)"
if uname -r | grep xanmod.*lts >/dev/null; then current="linux-xanmod-lts"; elif grep xanmod >/dev/null; then current="linux-xanmod";  else current="linux$major$minor"; fi
IFS=$'\n'


SHOW_DRIVER() {

if [ "$VIDEO_DRIVER_ENABLED" = "true" ]; then
  DRIVER_ENABLE_OR_DISABLE=$"Remover"
  INSTALL_OR_REMOVE_KERNEL="remove_kernel_now"

  if [ "$Kernel_version" = "$current" ]; then
    DISABLED_BUTTON="disabled"
    DRIVER_ENABLE_OR_DISABLE=$"Em uso"
  else
    DISABLED_BUTTON="remove-button"
    DISABLED_MESSAGE=""
  fi

else
  DRIVER_ENABLE_OR_DISABLE=$"Instalar"
  INSTALL_OR_REMOVE_KERNEL="install_kernel_now"
  DISABLED_BUTTON=""
  DISABLED_MESSAGE=""

fi
Kernel_version_CLEAN="$(echo "$Kernel_version" | sed 's|-| |g')"

if [ "$(echo "$Kernel_version" | grep -e linux419 -e linux54 -e linux510 -e linux515)" = "" ]; then
  Lts=""
else
  Lts=" - LTS"
fi

cat << EOF >> /tmp/kernel-mhwd-$Kernel_version.html

  <div class="app-card-kernel $CATEGORY Star">
    <div class="kernel_desc">
      $Kernel_version $Lts
      <div class="version">$(LANG=C pacman -Si $Kernel_version  | grep -i "^Version" | cut -f2 -d:)</div>
      $DESC
      </div>

    <div class="kernel-button">
    <a class="content-button status-button  $DISABLED_BUTTON" $DISABLED_BUTTON" onclick="disableBodyConfigSimple();" href="kernel.sh.htm?${INSTALL_OR_REMOVE_KERNEL}=${Kernel_version}">
      $DRIVER_ENABLE_OR_DISABLE
    </a>
  </div>
  </div>
EOF

}


VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE="$(mhwd-kernel -l | grep -vi kernels: | sed 's|.* ||g')"

# Show if installed
VIDEO_DRIVER_ENABLED_LIST="$(mhwd-kernel -li | grep -vi running | grep -vi kernels | sed 's|.* ||g')"

for i  in  $VIDEO_DRIVER_SHOW_ALL_AND_IF_IS_FREE; do

    Kernel_version="$(echo "$i" | cut -f1 -d" ")"
    VIDEO_DRIVER_OPEN="$(echo "$i" | cut -f2 -d" ")"

    if [ "$(echo "$VIDEO_DRIVER_ENABLED_LIST" | grep "^$Kernel_version$" )" != "" ]
    then
        VIDEO_DRIVER_ENABLED="true"
    else
        VIDEO_DRIVER_ENABLED="false"
    fi

SHOW_DRIVER "$Kernel_version" "$VIDEO_DRIVER_ENABLED" "$VIDEO_DRIVER_COMPATIBLE" "$VIDEO_DRIVER_OPEN" &

done

wait

IFS=$OIFS

