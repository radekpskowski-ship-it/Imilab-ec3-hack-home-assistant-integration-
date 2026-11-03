# Recording to an SMB share (NAS)

`miio_nas` uploads recordings to `<share>\xiaomi_camera_videos\<MAC>\YYYYMMDDHH\*.mp4`, including the backlog from the SD card.

**The camera only speaks SMB1** (libdsm, dialect `NT LM 0.12`). The server needs:

```ini
[global]
server min protocol = NT1
ntlm auth = yes
```

Modern Samba (default `SMB2_02`) and Windows refuse it — use a dedicated small Samba instance for the camera instead of weakening your main file server.

## miio methods (reverse engineered from `miio_nas` + `libmiio_samba.so`)

```
nas_list_dir   {"share": S}                     # lists directories = connection test
nas_set_config {"share": S, "state": 3|2, "sync_interval": 300|3600|86400, "video_retention_time": 604800|2592000|7776000|15552000|31104000}
nas_get_config {}                               # state 0 = not configured, 2 = off, 3 = on; addr returned as a little-endian int
nas_scan       {}                               # NetBIOS servers on the LAN
S = {"type":1, "name":"<NetBIOS name>", "addr":"<IP or LE int>", "dir":"<share>[\\subdir]", "group":"WORKGROUP", "user":"", "pass":""}
```

**Every key of `S` is required** — a missing `dir` gives error 22.

| Error code | Meaning |
|---|---|
| 11 | cannot connect (server unreachable or no SMB1) |
| 13 | wrong password / no access |
| 260 | server rejected the connection (e.g. unknown share) |
| 22 | invalid parameters |
| 2 | no such directory |

The Home Assistant integration exposes all of this: the options flow (tests the share before saving), the switch “Record to NAS”, the button “Test SMB connection”, and the sensors “NAS status” and “SMB test”.
