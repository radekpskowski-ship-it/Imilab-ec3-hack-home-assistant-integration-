# Video streaming

## Where the frames come from

`fetch_av` encodes the video and broadcasts every frame over **shbf** (a SigmaStar shared-buffer IPC, `libshbf` + `libshbfev` + libev) on Unix sockets in `/run`:

| Socket | Content |
|---|---|
| `/run/video_mainstream` | **H.265/HEVC Main, 2304×1296 @ 20 fps** (VENC ch1) |
| `/run/video_substream` | **H.265, 640×360 @ 20 fps** (VENC ch2) |
| `/run/jpeg_snap` | JPEG snapshots (VENC ch0, 1920×1080) |
| `/run/audio_in` | microphone |
| `/run/md_event` | motion events (see [reverse-engineering.md](reverse-engineering.md)) |

Each video message = **32-byte header + Annex-B payload**:

| Offset | Type | Meaning |
|---|---|---|
| 0 | u32 | type (1) |
| 4 | u32 | sequence number |
| 8 | u64 | PTS in µs |
| 16 | u32 | payload length (= message size − 32) |
| 20 | — | zeros |

A key frame is a single message containing VPS + SPS + PPS + IDR (the first NAL is `0x40`), with a GOP of ~56–60 frames (~3 s). Other frames are TRAIL_R (`02 01`).

Receiver API (from disassembly): `shbfev_rcv_create(loop, path)`, `shbfev_rcv_event(rcv, type, cb, userdata)` with type 1 = closed, 2 = video message, 3 = md_event message. The callback receives **`cb(userdata, buffer, …)`**, and every buffer must be released with `shbf_free()`.

## shbf2tcp

`src/shbf2tcp.c` (9.7 KB) subscribes to both video sockets and serves the raw HEVC over TCP — **8001 = main, 8002 = sub**. Every client starts at the next key frame, with a maximum of 4 clients per stream and a 256 KB buffer per client. A client that falls behind skips frames until the next IDR, so a slow consumer never blocks the camera. Several receivers on one shbf socket are fine, and Mi Home keeps working.

The camera has ~10 MB of free RAM and a load average of ~16 from the stock app alone, which is why it does no transcoding and serves raw frames only.

## go2rtc

See [`examples/go2rtc.yaml`](../examples/go2rtc.yaml). go2rtc pulls the TCP stream with ffmpeg (`-f hevc -use_wallclock_as_timestamps 1`) and serves RTSP/WebRTC. Only one connection goes to the camera, no matter how many viewers there are.

- HEVC over WebRTC works in Safari and in Chrome with hardware decoding. For everything else, use the transcoded `imilab_ec3_sub_h264` (640×360 is cheap to transcode).
- Bandwidth: sub ~40–80 kbit/s, main ~0.2–1 Mbit/s depending on the scene. With a weak signal (−85 dBm, ~130 kbit/s measured) only the sub stream is usable; at −50 dBm the main stream runs at ~18 fps.
