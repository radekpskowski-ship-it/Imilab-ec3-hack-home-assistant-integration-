# Local miio API (UDP 54321)

The camera answers the **legacy miio** protocol locally (python-miio `Device(ip, token).send(method, params)`). **MIoT `get_properties`/`set_properties` do not answer locally**, even with a proper `did`.

**The token changes on every boot.** Read it from nvram (`miio_token=` in `/mnt/data/.config.nvram`, 16 ASCII chars → hex) — `hack/bin/ha_cmd.sh token` does that.

The list of methods that can be called over the network is a table in `.rodata` of `miio_devicekit`:
`local.status local.bind miIO.restore local.time set_wdr set_night_mode restart_device set_power set_flip set_watermark set_light set_improve_program get_prop set_motion_region get_motion_region set_motion_detection_enable set_full_color set_motor update_log aec_auth miIO.config_loglevel set_motion_record getAlarmConfig setAlarmConfig alarm_sound get_favoritelocation set_favoritelocation set_focus_area_info get_focus_area_info get_eth0_status_info get_hotspot_info set_hotspot_info app_feedback_device_rpc get_properties set_properties action`
(plus `miIO.info` and the `nas_*` methods served by `miio_nas`). `set_mic_gain` and `motor_reset` exist only internally.

## Properties

`get_prop ["power","light","night_mode","flip","wdr","full_color","watermark","motion_record","improve_program","motion_detection_enable","motion_alarm","motion_region"]` — the remaining names return `"unknow"`.

| Method | Params | Notes |
|---|---|---|
| `set_power`, `set_light`, `set_wdr`, `set_flip`, `set_watermark`, `set_full_color`, `set_improve_program`, `set_motion_detection_enable` | `["on"]` / `["off"]` | |
| `set_night_mode` | `[0]` auto, `[1]` off, `[2]` on | |
| `set_motion_record` | `["on"]` record on motion, `["off"]` **record continuously**, `["stop"]` no recording | `off` ≠ disabled |
| `set_motion_region` | 32 integers (3 = high, 1 = low sensitivity per cell) | |
| `getAlarmConfig` / `setAlarmConfig` | `[mode, start_h, start_m, end_h, end_m, notify, interval_min]`, mode 0 off / 1 all day / 2 schedule | e.g. `[0,5,0,0,0,0,5]` |
| `set_motor` | `{"operation": 1}` left, `2` right, `3` up, `4` down | |
| `alarm_sound` | `[]` | siren |
| `restart_device` | `[]` | reboots the camera |
| `miIO.info` | `[]` | fw, MAC, RSSI (`ap.rssi`), uptime (`life`) |

## PTZ presets (slots 1–6)

```
set_favoritelocation [{"status":"set","location":1,"region":"[0,0,…32×0…]"}]   # save the current position
set_favoritelocation [{"status":"ctrl","location":1}]                         # go there
set_favoritelocation [{"status":"del","location":1}]                          # delete
get_favoritelocation []  → [{"location":1,"timet":…,"region":"[…]"}]
```

`region` is a 65-character string; all zeros = keep the current motion region.

## Siren on motion

`get_focus_area_info []` → `[{"focus_area":"off","focus_area_alarm":"off"}]`
`set_focus_area_info [{"focus_area":"off","focus_area_alarm":"on"}]`

**The parameter must be a list with one object.** A bare object crashes `miio_devicekit` (perp restarts it and the settings survive, but the camera stops answering for a while).

## Motion tracking

There is no miio method for it. Tracking is the mortox key `mem/default/track_switch` (`on`/`off`), watched by `miio_algo`:

```sh
LD_LIBRARY_PATH=/mnt/data/lib /mnt/data/bin/mortoxc set mem default track_switch on
```

The tracker has its own detector (it works with Mi Home motion detection off) and drives the pan motor. The `mem` layer is volatile, so tracking is off again after a reboot.

## NAS

See [nas-smb.md](nas-smb.md).
