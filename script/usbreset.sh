#!/bin/bash
# перегружает донгл по имени донгла

##u=$(/etc/zabbix/asterisk-zabbix-py/run.py dongle -f DataState -p $1 | sed 's/None//') && d=$(echo `udevadm info --name=$u --attribute-walk | sed -n 's/\s*ATTRS{\(\(devnum\)\|\(busnum\)\)}==\"\([^\"]\+\)\"/\4/p' | head -n 2 | awk '{$a = sprintf("%03d", $a); print}'` | tr " " "/") && echo $(sudo /root/script/usbreset /dev/bus/usb/$d | grep -c 'Reset successful')

if [ "$1" = "-n" ]
then
	u=$(/etc/zabbix/asterisk-zabbix-py/run.py dongle -f DataState -p $2 | sed 's/None//') 

elif [ "$1" = "-p" ]
then
	u=/dev/ttyUSB$2
else
	u=$1
fi
#echo $u

d=$(echo `udevadm info --name=$u --attribute-walk | sed -n 's/\s*ATTRS{\(\(devnum\)\|\(busnum\)\)}==\"\([^\"]\+\)\"/\4/p' | head -n 2 | awk '{$a = sprintf("%03d", $a); print}'` | tr " " "/")
echo $(sudo ./usbreset /dev/bus/usb/$d )
