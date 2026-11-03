# Imilab EC3 — local hack + Home Assistant integration

Local control and video for the **Imilab EC3** outdoor camera (CMSXJ25A, miio `chuangmi.camera.025b02`, board IPC025-B04, SigmaStar SSC325) **without replacing the firmware**: the stock Xiaomi app and Mi Home keep working, and the camera additionally gets:

- **SSH** (dropbear) — persistent, installed on the writable DATA partition;
- **RTSP / WebRTC** through go2rtc — a tiny `shbf2tcp` serves the camera's own H.265 streams (2304×1296 and 640×360) over TCP, with no transcoding on the camera;
- **motion events over MQTT**, read from the camera's own detector;
- a **Home Assistant integration** with ~46 entities: video, PTZ with presets, built-in motion tracking, night mode, SD/NAS recording, motion schedule and sensitivity, siren, restart, and CPU/RAM/SD/Wi-Fi diagnostics;
- documentation of the local miio API, the SMB (NAS) protocol and the internal IPC, from reverse engineering.

> ⚠️ You need to open the camera and solder to three UART pads **once**. Back up the whole flash first ([docs/backup-restore.md](docs/backup-restore.md)). Everything here is at your own risk.

## Features

| Area | What you get |
|---|---|
| **No cloud needed** | Everything below works locally. Mi Home keeps working in parallel, but you can block the cloud entirely. |
| **Video** | RTSP / WebRTC / HLS through go2rtc: main stream 2304×1296 and sub stream 640×360 (H.265, ~20 fps), optional H.264 sub stream transcoded by go2rtc; JPEG snapshots; `camera` entity in HA |
| **PTZ** | Pan left/right, up to 6 position presets (save / go to / delete, also as HA services), the camera's built-in **motion tracking** as a switch |
| **Image** | Camera on/off, night mode (auto/off/on), colour at night, WDR, flip image, timestamp watermark, status LED |
| **Motion** | Motion sensor over MQTT (from the camera's own detector), detection on/off, monitoring off / all day / schedule (from–until), alarm interval, sensitivity, siren on motion, Mi Home push on/off |
| **Recording** | SD card: continuous / on motion / off; upload to a NAS over SMB with retention — configured in the HA integration options, with a connection test and status sensor |
| **Other controls** | Siren, restart, sending logs to Xiaomi on/off |
| **Diagnostics** | Wi-Fi signal and quality, uptime, CPU, RAM, load, SD card state/size/free space, day/night mode, scene brightness, connection and stream-server sensors |
| **Access** | Root SSH with your keys (dropbear); HA gets its own key restricted to a single command |
| **Robustness** | OTA updates blocked by default; Wi-Fi from your own config with fallback networks; the hack and Wi-Fi survive a factory reset; the miio token, which changes on every boot, is refreshed automatically |
| **Safe to undo** | Kernel and ROOTFS are never modified; one file disables the hack; a full flash backup restores the stock state |

## Limitations

- Opening the camera and connecting UART is needed **once**, for the backup and the first install.
- The tested unit only **pans** — tilt is not available.
- **No AI detection** (person/pet/crying) — the stock firmware 4.0.4 only has pixel motion detection.
- **NAS upload needs SMB1** (`server min protocol = NT1`) — the camera cannot talk SMB2/3.
- H.265 playback depends on the client: Safari, the HA Android app and Chrome/Edge with hardware HEVC work, Firefox does not — use the H.264 sub stream there.
- The main stream needs a decent Wi-Fi signal (roughly −70 dBm or better); with a weak signal use the sub stream.
- Motion tracking is volatile — it is off again after a camera reboot (re-enable it with an automation).
- MIoT (`get_properties`) does not answer locally — the integration uses the legacy miio commands.
- The camera has ~10 MB of free RAM, so add-ons must stay small.

## How it works

```
Camera (stock firmware 4.0.4 + /mnt/data/hack)
 ├─ fetch_av ──shbf──> shbf2tcp :8001 main / :8002 sub (raw HEVC)
 │                        └──> go2rtc ──> RTSP / WebRTC ──> Home Assistant
 ├─ miio_algo ──/run/md_event──> miio_md ──> md2mqtt.sh ──> MQTT imilab_ec3/motion
 ├─ miio_devicekit / miio_nas ── local miio (UDP 54321, token) <── HA integration
 └─ dropbear :22 ── HA key forced to ha_cmd.sh (token | status | track)
```

The hack is started by one line added to `/mnt/data/bin/wifi_start.sh`. The kernel and ROOTFS are never modified.

## Steps

1. **Open the camera, connect UART** — [docs/uart.md](docs/uart.md) (where the pads are, wiring, U-Boot tricks).
2. **Back up the flash** — [docs/backup-restore.md](docs/backup-restore.md).
3. **Build and install the hack** (from an SD card, through U-Boot) — [docs/install.md](docs/install.md).
4. **Video**: go2rtc config — [docs/streaming.md](docs/streaming.md).
5. **Home Assistant**: SSH key + integration — [docs/home-assistant.md](docs/home-assistant.md).
6. Optional: **NAS recording** (SMB1 only!) — [docs/nas-smb.md](docs/nas-smb.md).

Reference: [hardware and firmware](docs/hardware.md) · [local miio API](docs/miio-api.md) · [reverse-engineering notes](docs/reverse-engineering.md)

## Repository layout

| Path | Content |
|---|---|
| `hack/` | scripts installed to `/mnt/data/hack` on the camera (+ `*.example` configs) |
| `src/` | C sources: `shbf2tcp`, `mdprobe`, `shbfprobe`, `shbfdump`, `unbuf`; link stubs for the vendor libraries |
| `build.sh` | cross-builds everything (Bootlin ARMv7 uClibc toolchain, static dropbear and mosquitto clients) |
| `tools/uart/` | U-Boot helper, flash dumper, SD-card installer (Python + pyserial) |
| `custom_components/imilab_ec3/` | Home Assistant integration |
| `examples/` | go2rtc and Home Assistant configuration |
| `docs/` | everything above in detail |

## Good to know

- **The miio token changes on every boot** — the integration fetches it over SSH automatically.
- **Wi-Fi is pinned** by `hack/etc/wifi.conf` (fallback networks supported). If you move the camera to another network, add it there first. The hack and the Wi-Fi settings survive a factory reset.
- **NAS upload needs SMB1** on the server.
- The tested unit only pans (no tilt), so the tilt buttons were left out.
- **OTA updates are blocked** by default (`touch /mnt/data/hack/allow_ota` to allow) — see [docs/install.md](docs/install.md#blocking-ota-on-by-default).
- MIoT (`get_properties`) does not answer locally, and person detection is not available in this firmware.

## Credits

- Board photo and initial findings: [linux-chenxing discussion #63](https://github.com/linux-chenxing/linux-chenxing.org/discussions/63) (photo © its author).
- [python-miio](https://github.com/rytilahti/python-miio), [go2rtc](https://github.com/AlexxIT/go2rtc), [dropbear](https://matt.ucc.asn.au/dropbear/dropbear.html), [mosquitto](https://mosquitto.org/), [Bootlin toolchains](https://toolchains.bootlin.com/).
- Prior art for Xiaomi cameras: [mija-framegrabber](https://github.com/telmomarques/mija-framegrabber), [yi-hack](https://github.com/roleoroleo).

## License

Code: MIT (see [LICENSE](LICENSE)). The board photo in `images/` belongs to its author (see [images/README.md](images/README.md)). Xiaomi/Imilab firmware is not included.
