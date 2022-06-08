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


SHOW_INSTALLED_PKG() {
# $CATEGORY
# $PKG
# $DESC

PKG_INSTALLED_OR_NOT=$"Remover"
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_without_verify_installed_$1_$PKG.html"

              <div class="app-card $CATEGORY">
                <span class="icon-cat icon-category-$CATEGORY" style="display:table-cell;"></span><span class="titlespan" style="display:table-cell;">
                  $PKG
                </span>
                <div class="app-card__subtext">
                  $DESC
                  </div>
                <div class="app-card-buttons">
                  <a class="content-button status-button remove-button" onclick="disableBodyConfigSimple();" href="index.sh.htm?remove_pkg_pamac=${PKG}">$PKG_INSTALLED_OR_NOT</a>
                </div>
              </div>
EOF

}



SHOW_NOT_INSTALLED_PKG() {
# $CATEGORY
# $PKG
# $DESC

PKG_INSTALLED_OR_NOT=$"Instalar"
cat << EOF >> "$HOME/.config/bigcontrolcenter-drivers/cache_without_verify_not_installed_$1_$PKG.html"

              <div class="app-card $CATEGORY">
                <span class="icon-cat icon-category-$CATEGORY" style="display:table-cell;"></span><span class="titlespan" style="display:table-cell;">
                  $PKG
                </span>
                <div class="app-card__subtext">
                  $DESC
                  </div>
                <div class="app-card-buttons">
                  <a class="content-button status-button" onclick="disableBodyConfigSimple();" href="index.sh.htm?install_pkg_pamac=${PKG}">$PKG_INSTALLED_OR_NOT</a>
                </div>
              </div>
EOF

}


  
# See PKGS to verify
ls -w1 -d $1/*/ | cut -f2 -d/ > "$HOME/.config/bigcontrolcenter-drivers/list_cache_without_verify_$1.html"






INSTALLED_PKGS="$(grep -xFf "$HOME/.config/bigcontrolcenter-drivers/total_pkgs" "$HOME/.config/bigcontrolcenter-drivers/list_cache_without_verify_$1.html")"

for PKG  in $INSTALLED_PKGS; do

  CATEGORY="$1"
  DESC="$(cat $1/$PKG/description)"

  SHOW_INSTALLED_PKG "$1" "$PKG" "$CATEGORY" "$DESC" &
done


NOT_INSTALLED_PKGS="$(grep -vxFf "$HOME/.config/bigcontrolcenter-drivers/total_pkgs" "$HOME/.config/bigcontrolcenter-drivers/list_cache_without_verify_$1.html")"

for PKG  in $NOT_INSTALLED_PKGS; do

  CATEGORY="$1"
  DESC="$(cat $1/$PKG/description)"

  SHOW_NOT_INSTALLED_PKG "$1" "$PKG" "$CATEGORY" "$DESC" &
done



IFS=$OIFS

