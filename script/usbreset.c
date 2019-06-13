/* usbreset -- send a USB port reset to a USB device

You invoke it as either:
  usbreset /proc/bus/usb/BBB/DDD
or
  usbreset /dev/usbB.D
*/

#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/usbdevice_fs.h>

int main(int argc, char **argv)
{
	const char *filename;
	int fd;
	int rc;

	if (argc != 2) {
		fprintf(stderr, "Usage: usbreset device-filename or  ./usbreset /proc/bus/usb/001/010\n");
		return 1;
	}
	filename = argv[1];

	fd = open(filename, O_WRONLY);
	if (fd < 0) {
		perror("Error opening output file");
		return 1;
	}

	printf("Resetting USB device %s\n", filename);
	rc = ioctl(fd, USBDEVFS_RESET, 0);
	if (rc < 0) {
		perror("Error in ioctl");
		return 1;
	}
	printf("Reset successful\n");

	close(fd);
	return 0;
}

/*
исходник http://marc.info/?l=linux-usb-users&m=116827193506484&w=2

Компилируем
gcc -o usbreset usbreset.c

или вар 2
$ wget https://gist.githubusercontent.com/x2q/5124616/raw -O usbreset.c
$ gcc -Wall -static -o usbreset usbreset.c
$ sudo install -o root -g root -m 0755 usbreset /usr/local/sbin

использование
[root@El-test ~]# lsusb | grep Huawei
Bus 002 Device 003: ID 12d1:1001 Huawei Technologies Co., Ltd. E169/E620/E800 HSDPA Modem

[root@El-test ~]# ./usbreset /proc/bus/usb/001/010
Resetting USB device /proc/bus/usb/002/003
Reset successful

*/
