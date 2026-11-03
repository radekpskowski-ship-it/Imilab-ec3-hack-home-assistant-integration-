# Hardware and firmware

| | |
|---|---|
| Camera | Imilab EC3 (CMSXJ25A), miio model `chuangmi.camera.025b02`, board **IPC025-B04** |
| SoC | SigmaStar **SSC325** (Infinity6, DT `INFINITY6 SSC009A-S01A`), Cortex-A7 ~800 MHz, 64 MB DDR2 (Linux gets ~38 MB) |
| Flash | 16 MB SPI NOR, EON/cFeon (JEDEC `1C 70 18`) |
| Sensor | GalaxyCore **GC2053** (2 MP) |
| Wi-Fi | MediaTek **MT7603U** (USB), driver `mt7603u_sta.ko` |
| PTZ | stepper motors driven from user space (`miio_algo` / `libdevice_kit`) through sysfs PWM 4–7 + GPIO; position stored in nvram as `motor=[h,v]`. The tested unit only pans. |
| Other | IR-cut + IR LEDs, white light, status LED, siren, microphone/speaker, SD card slot |
| Firmware | IPL `g2cd6de2`, U-Boot 2015.01 (`jenkins-ipc025b02_4_0_4_0097`), Linux 4.9.84, Buildroot 2017.08, uClibc, busybox 1.28.1, app version 4.0.4 |

## Flash layout

| mtd | Name | Range | Content |
|---|---|---|---|
| 0 | BOOT | 0x000000–0x050000 | IPL + IPL_CUST + U-Boot (xz), env @ 0x4F000 |
| 1 | KERNEL | 0x050000–0x250000 | uImage (lzma) |
| 2 | ROOTFS | 0x250000–0x9B0000 | squashfs 4.0 xz, read-only, ~5.6 MB used — **the tail from 0x800000 is free** |
| 3 | DATA | 0x9B0000–0xFE0000 | **jffs2, read-write, mounted at `/mnt/data`** — almost the whole Xiaomi application + nvram |
| 4 | CONFIG | 0xFE0000–0xFF0000 | practically empty |
| 5 | FACTORY | 0xFF0000–0x1000000 | model, did, miio key, Wi-Fi MAC, region |

Because the application lives on the writable DATA partition, the hack never touches ROOTFS or the kernel.

## Boot sequence

`linuxrc` → busybox init → `rcS` → `S00…S99`:

- `S09mstar_ko` — SigmaStar modules from **`/mnt/data/mstar_ko`**
- `S10ko` — `mt7603u_sta`, `exfat`
- `S41wifi` → **`/mnt/data/bin/wifi_start.sh`** ← the hack hooks in here (one line before `start $1`)
- `S49factory` — factory mode from SD, **requires an RSA signature** (not usable)
- `S50perp` / `S60service` — `perp` supervisor, services in `/mnt/data/etc/perp`
- `S61crond` — crontab from `/mnt/data/etc/crontab`
- `S99uboot_check` → `uboot_ota.sh` (updates U-Boot from `/mnt/data/BOOT.bin.gz`)

## Services (perp)

| Service | Role |
|---|---|
| `fetch_av` | capture + encode (MI_VENC), publishes frames over **shbf**: `/run/video_mainstream`, `/run/video_substream`, `/run/jpeg_snap`, `/run/audio_in` |
| `miio_client` / `miio_agent` | miio protocol (cloud + local UDP 54321) |
| `miio_devicekit` | device properties, local miio methods (night mode, light, motor, presets, alarms…) |
| `miio_algo` | motion detection (`/run/md_event`), tracking, IR-cut, WDR, **motor control** |
| `miio_cloud`, `miio_miss` | Mi Home streaming (TUTK P2P) and cloud events |
| `miio_record`, `miio_sdcard`, `miio_nas` | SD recording, SD management, SMB upload |
| `miio_ota` | OTA updates (`pre-ota.sh` / `post-ota.sh`) |
| `mortox` (`mortoxd`/`mortoxc`) | key-value store; layers `nvram` (persisted in `/mnt/data/.config.nvram`) and `mem` (volatile) |

## Security notes

- `root` is locked in `/etc/shadow`, there is no telnet/ssh, and the UART console prints logs only (no login).
- `log2mi.sh` uploads logs to `dlg.io.mi.com` hourly when `improve_program=on`.
- **The miio token changes on every boot** (stored in nvram as `miio_token`).
- Cloud domains: `ot.io.mi.com`, `ots.io.mi.com`, `otc.io.mi.com`, `dlg.io.mi.com`, `cm.iotcplatform.com`, `gm.iotcplatform.com`.
