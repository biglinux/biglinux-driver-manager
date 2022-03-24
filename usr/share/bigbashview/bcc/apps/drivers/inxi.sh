#!/bin/bash



DEVICE_INFO=$"Ver informações do dispositivo no Linux Hardware"
PCI_IDS="$(lspci -n | cut -f3 -d" ")"
USB_IDS="$(lsusb | cut -f6 -d" ")"


rm -f /tmp/hardwareinfo-inxi-*.html
rm -f /tmp/hardwareinfo-dmesg.html

if [ "$1" = "show" ]; then
  show="show"
fi


SHOW_HARDINFO() {

# $1 CATEGORY_INXI
# $2 NAME
# $3 ICON

echo "<div class=\"app-card $CATEGORY\" style=\"max-height: 100%;\">" >> /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html
echo "<div class=\"app-card__title\">$NAME</div>" >> /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html
echo '<div class="app-card__subtext">' >> /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html

$PKEXEC inxi ${PARAMETER_INXI}${CATEGORY_INXI} -y 100 --indents 5 | grep '     ' | sed 's|          ||g' | tr '\n ' ' ' | sed 's|      |\n     |g' | ansi2html -f 18px -l | sed 's|           <span class="|<span class="subcategory1 |g' | grep -A 9999 '<pre class="ansi2html-content">' | grep -v '</html>' | grep -v '</body>' | sed 's|<pre class="ansi2html-content">||g;s|</pre>||g;s|<span class="ansi1 ansi34">|<br><span class="ansi1 ansi34">|g;s|     |</div><div class=hardwareSpace>|g;s|</div><br><span class="ansi1 ansi34">|</div><span class="hardwareTitle2">|g' >> /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html

echo '</div></div>' >> /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html


for i  in  $(grep -i Chip-ID /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html | sed 's| <br><span class="ansi1 ansi34">class-ID.*||g' | rev | cut -f1 -d" " | rev | sort -u); do
  if [ "$(echo "$PCI_IDS" | grep "$i")" != "" ]; then

      sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run pci:$(echo $i | sed 's|:|-|g')')\">$DEVICE_INFO</a></div>|g" /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html

  elif [ "$(echo "$USB_IDS" | grep "$i")" != "" ]; then

      sed -i "s|$i|$i<div><button class=\"content-button\" onclick=\"_run('./linuxHardware.run usb:$(echo $i | sed 's|:|-|g')')\">$DEVICE_INFO</a></div>|g" /tmp/hardwareinfo-inxi-${CATEGORY_INXI}.html
  fi

done


}

  CATEGORY_INXI="cpu"
  PARAMETER_INXI="-c 2 -a -xx --"
  CATEGORY="cpu"
  NAME=$"Processador"
  ICON="cpu"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  #Clean CPU
  grep -ve 'Vulnerabilities:' -ve 'Type:' /tmp/hardwareinfo-inxi-cpu.html > /tmp/hardwareinfo-inxi-cpu2.html
  mv -f /tmp/hardwareinfo-inxi-cpu2.html /tmp/hardwareinfo-inxi-cpu.html


  CATEGORY_INXI="machine"
  if [ "$show" = "show" ]; then
    PARAMETER_INXI="-c 2 -a -xx --"
  else
    PARAMETER_INXI="-c 2 -x -z --"
  fi
  NAME=$"Placa mãe"
  CATEGORY="machine"
  ICON="machine"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  if [ "$show" = "show" ]; then
    PARAMETER_INXI="-c 2 -a -xx --"
  else
    PARAMETER_INXI="-c 2 -x -z --"
  fi
  CATEGORY_INXI="memory"
  NAME=$"Memória"
  CATEGORY="memory"
  ICON="memory"
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="swap"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Swap (Memória Virtual)"
  CATEGORY="memory"
  ICON="swap"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="graphics"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Gráficos"
  CATEGORY="gpu"
  ICON="graphics"
  PKEXEC="pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY"
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="audio"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Áudio"
  CATEGORY="audio"
  ICON="audio"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="network-advanced"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Rede"
  CATEGORY="Network"
  ICON="network"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="ip"
  if [ "$show" = "show" ]; then
    PARAMETER_INXI="-c 2 -a -xx --"
  else
    PARAMETER_INXI="-c 2 -x -z --"
  fi
  NAME=$"Conexões de Internet"
  CATEGORY="network"
  ICON="ip"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="usb"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Dispositivos e conexões USB"
  CATEGORY="usb"
  ICON="usb"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="slots"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Portas PCI"
  CATEGORY="pci"
  ICON="usb"
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="battery"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Bateria"
  CATEGORY="battery"
  ICON="battery"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="disk-full"
  if [ "$show" = "show" ]; then
    PARAMETER_INXI="-c 2 -a -xx --"
  else
    PARAMETER_INXI="-c 2 -x -z --"
  fi
  NAME=$"Dispositivos de armazenamento"
  CATEGORY="disk"
  ICON="disk"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="partitions-full"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Partições montadas"
  CATEGORY="disk"
  ICON="disk"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="unmounted"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Partições desmontadas"
  CATEGORY="disk"
  ICON="disk"
  PKEXEC="pkexec -u $BIGUSER"
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  
  
#   
# for i  in  $(smartctl --scan | cut -f1 -d" "); do
# 
# 
# echo "<div class=\"app-card disk\" style=\"max-height: 100%;\">" >> /tmp/hardwareinfo-inxi-SMART.html
# echo "<div class=\"app-card__title\">SMART $i</div>" >> /tmp/hardwareinfo-inxi-SMART.html
# echo '<div class="app-card__subtext">' >> /tmp/hardwareinfo-inxi-SMART.html
# 
# 
# 
# cat << EOF >> /tmp/hardwareinfo-inxi-SMART.html
# $(sudo smartctl -i --all $i | grep -e "Model Family" -e "Device Model" -e "Serial Number" -e "Firmware Version" -e "User Capacity" -e "Sector Size" -e "Rotation Rate" -e "ATA Version is" -e "SMART support is" -e "Power_On_Hours" -e "Power_Cycle_Count" -e "Airflow_Temperature_Cel" -e "Temperature_Celsius" | sed 's|0x00.*  -  ||g;s|.*Power_On_Hours|Power_On_Hours:</span>|g;s|.*Power_Cycle_Count|Power_Cycle_Count:</span>|g;s|.*Airflow_Temperature_Cel|Airflow_Temperature_Cel:</span>|g;s|.*Temperature_Celsius|Temperature_Celsius:</span>|g;s|^|<br><span class="ansi1 ansi34">|g;s|: |: </span>|g')
# 
# </textarea></div></div>
# EOF
# 
# 
# done

  # Save dmesg
  dmesg | grep -i -e erro > /tmp/hardwareinfo-dmesg.html
  
  
  
  CATEGORY_INXI="logical"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Dispositivos lógicos"
  CATEGORY="disk"
  ICON="disk"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="raid"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Raid"
  CATEGORY="disk"
  ICON="disk"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="system"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Sistema"
  CATEGORY="system"
  ICON="disk"
  PKEXEC=""

  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 
  PARAMETER_INXI="-c 2 -a -xx --"
  CATEGORY_INXI="info"
  NAME=$"Informações"
  CATEGORY="system"
  ICON="disk"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="repos"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Repositórios"
  CATEGORY="system"
  ICON="disk"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="bluetooth"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Bluetooth"
  CATEGORY="bluetooth"
  ICON="disk"
  PKEXEC=""
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 

  CATEGORY_INXI="sensors"
  PARAMETER_INXI="-c 2 -a -xx --"
  NAME=$"Temperatura"
  CATEGORY="sensors"
  ICON="disk"
  PKEXEC="pkexec -u $BIGUSER env DISPLAY=$BIGDISPLAY XAUTHORITY=$BIGXAUTHORITY"
  SHOW_HARDINFO "$PARAMETER_INXI" "$CATEGORY_INXI" "$NAME" "$ICON" "$CATEGORY" $show 
