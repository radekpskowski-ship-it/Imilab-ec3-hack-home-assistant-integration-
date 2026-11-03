# Imilab EC3 — local hack + Home Assistant integration

Local control and video for the **Imilab EC3** outdoor camera (CMSXJ25A, miio `chuangmi.camera.025b02`, board IPC025-B04, SigmaStar SSC325) **without replacing the firmware**: the stock Xiaomi app and Mi Home keep working, and the camera additionally gets:

- **SSH** (dropbear) — persistent, installed on the writable DATA partition;
- **RTSP / WebRTC** through go2rtc — a tiny `shbf2tcp` serves the camera's own H.265 streams (2304×1296 and 640×360) over TCP, with no transcoding on the camera;
- **motion events over MQTT**, read from the camera's own detector;
- a **Home Assistant integration** with ~46 entities: video, PTZ with presets, built-in motion tracking, night mode, SD/NAS recording, motion schedule and sensitivity, siren, restart, and CPU/RAM/SD/Wi-Fi diagnostics;
- documentation of the local miio API, the SMB (NAS) protocol and the internal IPC, from reverse engineering.

> ⚠️ You need to open the camera and solder to three UART pads **once**. Back up the whole flash first ([docs/backup-restore.md](docs/backup-restore.md)). Everything here is at your own risk.

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
