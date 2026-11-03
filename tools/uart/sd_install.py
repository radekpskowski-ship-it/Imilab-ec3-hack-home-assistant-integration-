#!/usr/bin/env python3
"""Install hack.tgz from a FAT32 SD card through U-Boot — no shell on the camera needed.

1. Copy out/hack.tgz to the root of a FAT32 SD card and insert it into the camera.
2. Connect UART, run this script, then power-cycle the camera.

What it does:
  catch U-Boot → fatload hack.tgz to RAM → crc32 check → write it to the unused tail of ROOTFS
  (flash 0x800000; the squashfs image ends at ~0x7F2000) → verify → boot once with
  init=/bin/sh -c "mount DATA; extract the package from mtdblock2; run hack/install.sh; reboot"
  (the kernel ignores UART RX, so the commands have to be passed on the kernel command line).
Nothing is written to U-Boot env (no saveenv) — the next boot is a normal one.
"""
import argparse
import sys
import time
import zlib

import serial

from uboot import catch, cmd

RAM = 0x21000000
OFF = 0x800000
ROOTFS_START = 0x250000
BASE_ARGS = ("console=ttyS0,115200 root=/dev/mtdblock2 rootfstype=squashfs ro init=/bin/sh "
             "LX_MEM=0x3fc6000 mma_heap=mma_heap_name0,miu=0,sz=0x1400000")


def watch(ser: serial.Serial, seconds: float, stop: bytes) -> str:
    buf = b""
    end = time.time() + seconds
    while time.time() < end:
        buf += ser.read(65536)
        if stop in buf:
            break
    return buf.decode(errors="replace").replace("\r", "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("package", nargs="?", default="out/hack.tgz")
    ap.add_argument("--port", default="/dev/ttyUSB0")
    a = ap.parse_args()
    data = open(a.package, "rb").read()
    size, crc = len(data), f"{zlib.crc32(data) & 0xffffffff:08x}"
    elen = (size + 0xffff) // 0x10000 * 0x10000
    # U-Boot here is not hush: max 32 args per command and no quoting inside — keep spaces to a minimum
    script = ("mount -t jffs2 /dev/mtdblock3 /mnt/data&&"
              f"dd if=/dev/mtdblock2 bs=64k skip={(OFF - ROOTFS_START) // 0x10000} count={elen // 0x10000}"
              f"|head -c {size}|gunzip|tar xf - -C /mnt/data&&sh /mnt/data/hack/install.sh;"
              "sync;umount /mnt/data;reboot -f")
    print(f"package {size} B crc {crc} → flash {OFF:#x}; power-cycle the camera now")
    with serial.Serial(a.port, 115200) as ser:
        catch(ser)
        cmd(ser, "mmc rescan", 15)
        if "hack.tgz" not in cmd(ser, "fatls mmc 0", 15):
            sys.exit("hack.tgz not found on the SD card")
        cmd(ser, f"mw.b {RAM:x} ff {elen:x}")
        cmd(ser, f"fatload mmc 0 {RAM:x} hack.tgz", 30)
        if crc not in cmd(ser, f"crc32 {RAM:x} {size:x}"):
            sys.exit("CRC mismatch in RAM — flash untouched")
        cmd(ser, "sf probe 0")
        cmd(ser, f"sf erase {OFF:x} {elen:x}", 60)
        cmd(ser, f"sf write {RAM:x} {OFF:x} {elen:x}", 60)
        cmd(ser, f"mw.b {RAM:x} 0 {elen:x}")
        cmd(ser, f"sf read {RAM:x} {OFF:x} {elen:x}", 60)
        if crc not in cmd(ser, f"crc32 {RAM:x} {size:x}"):
            sys.exit("CRC mismatch after writing!")
        cmd(ser, f"setenv hb {BASE_ARGS}")
        cmd(ser, f"setenv hs '\"{script}\"'")
        cmd(ser, "setenv bootargs ${hb} -- -c ${hs}")
        if script not in cmd(ser, "printenv bootargs"):
            sys.exit("bootargs incomplete — not starting the installer")
        ser.write(b"run bootcmd\n")
        out = watch(ser, 120, b"hack-install: DONE")
        print("installer:", "DONE" if "hack-install: DONE" in out else "no DONE (check the log)")
        out = watch(ser, 150, b"hack: dropbear started")
        print("normal boot:", "dropbear started" if "dropbear started" in out else "no dropbear yet")


if __name__ == "__main__":
    main()
