#!/bin/sh
# Local hack services (started from boot.sh). Logs only in /tmp (DATA is jffs2).
HACK=/mnt/data/hack
export LD_LIBRARY_PATH=/mnt/data/lib:/lib:/usr/lib

# shbf2tcp: raw HEVC from fetch_av, TCP 8001 = main 2304x1296, 8002 = sub 640x360 (→ go2rtc)
if [ ! -f $HACK/disable_shbf2tcp ] && ! pidof shbf2tcp >/dev/null; then
    while :; do
        $HACK/bin/shbf2tcp 8001 8002 >>/tmp/shbf2tcp.log 2>&1
        tail -n 50 /tmp/shbf2tcp.log >/tmp/shbf2tcp.log.1 && mv /tmp/shbf2tcp.log.1 /tmp/shbf2tcp.log
        sleep 5
    done &
fi

# md2mqtt: motion events → MQTT (settings in hack/etc/mqtt.conf)
if [ ! -f $HACK/disable_md2mqtt ] && [ -f $HACK/etc/mqtt.conf ] && ! ps | grep -v grep | grep -q md2mqtt.sh; then
    setsid $HACK/bin/md2mqtt.sh </dev/null >/dev/null 2>&1 &
fi
