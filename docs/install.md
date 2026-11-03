# Installing the hack

The hack is a directory `/mnt/data/hack` on the writable DATA partition plus **one line** added to `/mnt/data/bin/wifi_start.sh`. It survives reboots, and the stock firmware and Mi Home keep working.

## 1. Build

```sh
./build.sh          # downloads the Bootlin ARMv7 uClibc toolchain, dropbear and mosquitto into .cache/
```

`out/hack/bin` then contains: `dropbearmulti` (SSH), `mosquitto_pub/sub`, `shbf2tcp`, `shbfprobe`, `shbfdump`, `mdprobe`, plus `out/hack/lib/libunbuf.so`.
The vendor libraries (`libshbf`, `libshbfev`, `libev`) are **not** redistributed — `src/stubs.c` provides link-time stubs, and the real ones from `/mnt/data/lib` are used at run time.

## 2. Your settings

```sh
cp hack/etc/wifi.conf.example   hack/etc/wifi.conf            # Wi-Fi the camera should join
cp hack/etc/mqtt.conf.example   hack/etc/mqtt.conf            # broker for motion events
cp hack/etc/shadow.example      hack/etc/shadow               # root password hash (openssl passwd -1)
cp hack/root/.ssh/authorized_keys.example hack/root/.ssh/authorized_keys   # your public key(s)
./build.sh pack     # → out/hack.tgz
```

`wifi.conf` overrides the network stored by Mi Home. **The camera will only join the networks listed there** (you can add fallback networks, see below) — if you move the camera, update the file first (or you will need the UART again).

## 3. Install from an SD card (UART needed once)

1. Format an SD card as FAT32 and copy `out/hack.tgz` to its root. Insert it into the camera.
2. Connect the UART (see [uart.md](uart.md)).
3. `tools/uart/sd_install.py out/hack.tgz` and power-cycle the camera.

The script catches U-Boot, loads the package from the SD card, stores it in the unused tail of the ROOTFS partition (0x800000), verifies it, and boots **once** with `init=/bin/sh -c "…"`. That one-shot shell unpacks the package to `/mnt/data`, runs `hack/install.sh` (adds the hook and backs up the original `wifi_start.sh` as `.orig`) and reboots. The next boot is a normal one with the hack active.

## 4. First login

```sh
ssh root@<camera-ip>
```

dropbear runs on port 22 and the host keys are kept in `/mnt/data/hack/etc`. There is no SFTP server, so `scp` does not work — copy files with `cat file | ssh root@cam 'cat > /tmp/file'`.

## Files on the camera

| File | Role |
|---|---|
| `hack/wifi_hook.sh` | sourced by `wifi_start.sh`: Wi-Fi override + starts `boot.sh` |
| `hack/boot.sh` | bind-mounts `/etc/shadow` and `/root`, starts dropbear, blocks OTA, starts `local.sh` |
| `hack/etc/miio_ota.rc.main` | replacement perp script for `miio_ota` (OTA block) |
| `hack/local.sh` | starts `shbf2tcp` (respawn loop) and `md2mqtt.sh` |
| `hack/bin/ha_cmd.sh` | forced command for the Home Assistant SSH key: `token`, `status`, `track on/off` |
| `hack/bin/md2mqtt.sh` | motion events → MQTT |

Switches: `touch /mnt/data/hack/disable` (whole hack), `disable_shbf2tcp`, `disable_md2mqtt`, `allow_ota`.

## Updating later

Everything after the first install happens over SSH, for example:

```sh
cat out/hack/bin/shbf2tcp | ssh root@cam 'cat > /mnt/data/hack/bin/shbf2tcp.new && mv /mnt/data/hack/bin/shbf2tcp.new /mnt/data/hack/bin/shbf2tcp'
```

DATA is jffs2 on NOR flash — avoid frequent writes (keep logs in `/tmp`).

## Blocking OTA (on by default)

A firmware update from Xiaomi can rewrite DATA and remove the hack, so `boot.sh` blocks OTA on every boot, without any DNS filtering:

- the perp service `miio_ota` gets a replacement `rc.main` (from `hack/etc/miio_ota.rc.main`; the original is saved as `/mnt/data/etc/perp/miio_ota/rc.main.orig`) that runs `sleep` instead of `miio_ota`. `boot.sh` runs from `S41wifi`, before `S50perp`, so this applies on the same boot. Disabling the service with `perpctl d` or the sticky bit is not enough — perp re-activates every service when it starts;
- once perpd is up, `boot.sh` kills any `miio_ota` that started anyway and turns `/mnt/data/BOOT.bin.gz` into a directory, so `uboot_ota.sh` (from `S99uboot_check`) never flashes a new U-Boot.

To allow an update: `touch /mnt/data/hack/allow_ota` and reboot. Remove the file and reboot to block it again.

## Factory reset and Wi-Fi

- While `hack/etc/wifi.conf` exists, `wifi_hook.sh` always starts the camera in station mode (`set -- ENTER_STA_MODEL`), so it does not open the pairing hotspot after a factory reset. A reset (button or `miIO.restore`) clears only nvram (Wi-Fi, Mi account binding, token); `/mnt/data/hack` and the hook stay. Mi Home has to be paired again.
- Fallback networks: add `ssid2`/`passwd2`, `ssid3`/`passwd3`… to `wifi.conf` (priority 10, 9, 8…; an empty password means an open network). Changes apply on the next reboot. The camera does not move back to the main network by itself while a fallback one works.
