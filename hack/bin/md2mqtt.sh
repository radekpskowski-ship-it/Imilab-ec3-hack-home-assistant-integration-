#!/bin/sh
# Motion events from /run/md_event (miio_md) → MQTT <topic>/motion (at most every 3 s).
# Events only flow with motion detection on and monitoring != off (setAlarmConfig).
HACK=/mnt/data/hack
. $HACK/etc/mqtt.conf
export LD_LIBRARY_PATH=/mnt/data/lib:/lib:/usr/lib
pub() {
    $HACK/bin/mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -u "$MQTT_USER" -P "$MQTT_PASS" -q 1 -t "$MQTT_TOPIC/$1" -m "$2" $3
}
last=0
while :; do
    LD_PRELOAD=$HACK/lib/libunbuf.so /mnt/data/bin/miio_md 2>/dev/null | while read -r _ _ ts; do
        now=$(cut -d. -f1 /proc/uptime)
        if [ $((now - last)) -ge 3 ]; then
            pub motion "{\"ts\":\"${ts#=}\"}"
            last=$now
        fi
    done
    sleep 5
done
