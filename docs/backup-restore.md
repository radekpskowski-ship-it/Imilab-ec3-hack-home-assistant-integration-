# Backup and restore

**Back up the whole flash before changing anything.** It is the only way back if something goes wrong.

## Dump the 16 MB NOR over UART

1. Catch U-Boot: `tools/uart/uboot.py catch` and power-cycle the camera.
2. Load the chip into RAM: `tools/uart/uboot.py cmd "sf probe 0" && tools/uart/uboot.py cmd "sf read 0x21000000 0 0x1000000" --timeout 60`
3. Note the checksum: `tools/uart/uboot.py cmd "crc32 0x21000000 0x1000000" --timeout 60`
4. Dump: `tools/uart/dump_flash.py --out backup` (≈1 h 45 min, resumable). Every 64 KB block is verified against U-Boot's CRC32.
5. Compare `crc32 backup/nor16m.bin` with step 3 and split it into partitions:

```sh
dd if=backup/nor16m.bin of=backup/mtd_BOOT.bin    bs=64k skip=0   count=5
dd if=backup/nor16m.bin of=backup/mtd_KERNEL.bin  bs=64k skip=5   count=32
dd if=backup/nor16m.bin of=backup/mtd_ROOTFS.bin  bs=64k skip=37  count=118
dd if=backup/nor16m.bin of=backup/mtd_DATA.bin    bs=64k skip=155 count=99
dd if=backup/nor16m.bin of=backup/mtd_CONFIG.bin  bs=64k skip=254 count=1
dd if=backup/nor16m.bin of=backup/mtd_FACTORY.bin bs=64k skip=255 count=1
```

The FACTORY partition contains the device key and the DATA partition contains your Wi-Fi password and miio token — keep the backup private.

## Restore (per partition, from an SD card)

The whole 16 MB image does not fit in RAM next to U-Boot, so restore partition by partition. Example for DATA (the only partition the hack changes):

```
mmc rescan
fatload mmc 0 0x21000000 mtd_DATA.bin
sf probe 0
sf erase 0x9B0000 0x630000
sf write 0x21000000 0x9B0000 0x630000
reset
```

To just undo the hack without reflashing: `touch /mnt/data/hack/disable` (skips everything) or copy back the original hook with `cp /mnt/data/bin/wifi_start.sh.orig /mnt/data/bin/wifi_start.sh`.
