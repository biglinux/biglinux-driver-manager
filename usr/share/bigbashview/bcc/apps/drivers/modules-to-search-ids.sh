#!/bin/bash

##############
# Extract ids from modules
# By Bruno Goncalves < www.biglinux.com.br >
# 2022/03/01
# License GPL V2 or greater
###############

for pkgs  in  "8192eu" "8821ce" "8192cu" "8812au" "8821cu" "8821au" "8188eu" "rtl8188fu" "8814au" "r8101" "8723bu" "r8168"; do

echo "$pkgs"
./extract-ids-modules $pkgs

done





