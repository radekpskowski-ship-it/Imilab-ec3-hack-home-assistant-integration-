# Home Assistant integration

`custom_components/imilab_ec3` creates **one device with ~46 entities**. It uses local miio for control, go2rtc for video, MQTT for motion and SSH for the camera's system status. Entity names are translated (English, Polish).

## Requirements

- the hack installed on the camera ([install.md](install.md));
- [go2rtc](https://github.com/AlexxIT/go2rtc) with [`examples/go2rtc.yaml`](../examples/go2rtc.yaml) (a standalone instance — HA's built-in one has no API for snapshots);
- an MQTT broker configured in HA (for the motion sensor);
- `python-miio` — already shipped with the HA container image (0.5.12).

## SSH key for Home Assistant

The token changes on every camera boot, so HA fetches it over SSH with its own key, which can **only** run `hack/bin/ha_cmd.sh`:

```sh
docker exec homeassistant ssh-keygen -q -t ed25519 -N "" -C ha-imilab-token -f /config/imilab/ssh_key
docker exec homeassistant cat /config/imilab/ssh_key.pub
# on the camera, append to /mnt/data/hack/root/.ssh/authorized_keys:
command="/mnt/data/hack/bin/ha_cmd.sh",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty ssh-ed25519 AAAA… ha-imilab-token
```

Test it: `docker exec homeassistant ssh -i /config/imilab/ssh_key root@<camera> status` should print JSON.

## Install

Copy `custom_components/imilab_ec3` to `/config/custom_components/`, restart HA, then either add the integration in the UI (Settings → Devices & services → Add → Imilab EC3) or use the YAML package [`examples/imilab_ec3.yaml`](../examples/imilab_ec3.yaml). With an empty token, the integration fetches it over SSH. **Configure** opens the NAS (SMB) settings.

## Entities

| Group | Entities |
|---|---|
| Video | camera (stream from go2rtc, snapshot from `/api/frame.jpeg`) |
| Motion | Motion (MQTT, off 20 s after the last event; attributes `last_motion`, `detector_active`), Motion tracking |
| Detection | Motion detection, Monitoring (off / all day / schedule), Monitoring from/until, Motion alarm interval, Push notifications (Mi Home), Motion sensitivity, Siren on motion |
| Image | Camera on/off, Night mode, Color at night, WDR, Flip image, Timestamp watermark, Status LED |
| Recording | SD recording (continuous / on motion / disabled), Record to NAS, Test SMB connection, NAS status, SMB test |
| PTZ | Pan left/right, PTZ preset, Save position as preset, PTZ presets; services `imilab_ec3.save_preset / goto_preset / delete_preset` |
| Other | Siren, Restart, Send logs to Xiaomi |
| Diagnostics | Wi-Fi signal and quality, uptime, CPU, RAM, free RAM, load, SD card (state/size/free/used), day/night mode, scene brightness (EV), connection, stream server |

## Motion — what has to be on

The detector in `miio_algo` publishes to `/run/md_event` only when **Motion detection = on** and **Monitoring ≠ off**. Push notifications can stay off, so Mi Home does not notify anyone. `md2mqtt.sh` forwards the events (at most every 3 s) to `imilab_ec3/motion`.

**Motion tracking** is independent: it has its own detector and pans the camera even with detection off. It is volatile — re-enable it after a camera reboot (e.g. with an automation on the Connection sensor).

## Automation example

```yaml
alias: Re-enable tracking after the camera reboots
triggers:
  - trigger: state
    entity_id: binary_sensor.imilab_ec3_connection
    to: "on"
actions:
  - delay: "00:01:00"
  - action: switch.turn_on
    target:
      entity_id: switch.imilab_ec3_motion_tracking
```

(The entity ids depend on your HA language.)
