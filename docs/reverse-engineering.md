# Reverse-engineering notes

Tools: the Bootlin toolchain's `arm-linux-objdump`/`readelf`, plus small Python helpers that resolve literal-pool strings (the binaries are ARM mode, not Thumb — use `objdump -b binary -m arm --adjust-vma=…` when symbols are missing).

## shbf

- Video: event type **2**, `cb(userdata, buf, …)`, 32-byte header + Annex-B (see [streaming.md](streaming.md)).
- `/run/md_event`: event type **3** (`miio_md` uses the `shbf_mde_client_*` wrappers). Each message is just an **8-byte timestamp** — one message = motion detected. Messages arrive every 0.2–1.3 s while there is motion.
- `miio_md` prints `[md_on_message] timestamp =…` with `printf`. Piping it needs `LD_PRELOAD=libunbuf.so` (line buffering).

## mortox (key-value store)

`mortoxc set|get|list [layer] [group] key value`. Layers used by `miio_algo` (`kv_sys_callback_init`):

| Layer | Keys watched |
|---|---|
| `nvram` | `motion_region`, `night_mode`, `full_color`, `wdr`, `power` |
| `mem` | `track_switch` |

`nvram` is persisted in `/mnt/data/.config.nvram`, while `mem` is lost on reboot.

## Motion tracking

`notify_cb_track_mode` → `track_mode_config(on/off)`. While tracking, `miio_algo` logs `[kv_client_set_kv]set value=track` and drives the PWM motor group (kernel log `group_round_in (pwm_id, round) = (1, N)`).

## Day / night

`miio_algo` logs every ~30 s: `___day mode____2color=1,ev_attr.ev=43,…` or `___night mode____ new2 ev=117,…` (the EV scales differ between modes). `ha_cmd.sh status` parses the last line of `/tmp/messages*`.

## miio_nas / libmiio_samba

- The `nas_list_dir` handler requires `params.share.type`, picks backend 1 = `share_samba`, whose JSON parser requires `name, addr, dir, group, user, pass` (`addr` either as an int or as a dotted string, via `inet_aton`).
- libdsm only negotiates `NT LM 0.12` (SMB1).

## Not available

- MIoT `get_properties` locally — no answer.
- Person/pet/crying detection — not in firmware 4.0.4 (only pixel motion; there is a dead `face_det_tsk` string).
- SoC temperature sensor.
