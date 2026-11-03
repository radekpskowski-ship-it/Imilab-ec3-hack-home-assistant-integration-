#!/bin/sh
# Commands for Home Assistant (key /config/imilab/ssh_key, command= in authorized_keys).
#   token  — current miio token (hex; changes on every camera boot)
#   status — JSON: CPU, RAM, load, uptime, SD card, Wi-Fi, day/night + EV, tracking, hack services
#   track on|off — motion tracking (mortox mem/default/track_switch → miio_algo; volatile, lost on reboot)
mortoxc() { LD_LIBRARY_PATH=/mnt/data/lib:/lib:/usr/lib /mnt/data/bin/mortoxc "$@"; }
case "$SSH_ORIGINAL_COMMAND" in
"track on"|"track off")
    mortoxc set mem default track_switch "${SSH_ORIGINAL_COMMAND#track }" >/dev/null && mortoxc get mem default track_switch
    ;;
token|"")
    grep -a -o "miio_token=[^ ]*" /mnt/data/.config.nvram | head -1 | cut -c12- | head -c 16 | od -An -tx1 | tr -d " \n"
    echo
    ;;
status)
    read -r _ u1 n1 s1 i1 w1 q1 sq1 _ < /proc/stat
    sleep 1
    read -r _ u2 n2 s2 i2 w2 q2 sq2 _ < /proc/stat
    busy=$(( (u2+n2+s2+q2+sq2) - (u1+n1+s1+q1+sq1) ))
    total=$(( busy + (i2+w2) - (i1+w1) ))
    cpu=$(( total > 0 ? busy * 100 / total : 0 ))
    mem_total=$(awk '/^MemTotal/{print $2}' /proc/meminfo)
    mem_avail=$(awk '/^MemAvailable/{print $2}' /proc/meminfo)
    load=$(cut -d" " -f1 /proc/loadavg)
    uptime=$(cut -d. -f1 /proc/uptime)
    if grep -q " /mnt/sdcard " /proc/mounts; then
        set -- $(df -k /mnt/sdcard | tail -1)
        sd="{\"mounted\":true,\"total_kb\":$2,\"used_kb\":$3,\"free_kb\":$4}"
    else
        sd="{\"mounted\":false}"
    fi
    set -- $(tail -1 /proc/net/wireless)
    wq=${3%.}; wl=${4%.}
    # miio_algo logs every ~30 s: day "___day mode____2color=1,ev_attr.ev=43,...", night "___night mode____ new2 ev=117,..."
    dn=$(cat /tmp/messages.0 /tmp/messages 2>/dev/null | grep "___[a-z]* mode____" | tail -1)
    if [ -n "$dn" ]; then echo "$dn" > /tmp/ha_daynight; else dn=$(cat /tmp/ha_daynight 2>/dev/null); fi
    mode=$(echo "$dn" | sed -n 's/.*___\([a-z]*\) mode.*/\1/p')
    ev=$(echo "$dn" | sed -n 's/.*[ .]ev=\([0-9]*\).*/\1/p')
    pidof shbf2tcp >/dev/null && rtsp=true || rtsp=false
    [ "$(mortoxc get mem default track_switch 2>/dev/null)" = on ] && track=true || track=false
    echo "{\"cpu\":$cpu,\"mem_total_kb\":$mem_total,\"mem_avail_kb\":$mem_avail,\"load\":$load,\"uptime\":$uptime,\"sd\":$sd,\"wifi_quality\":${wq:-0},\"wifi_level\":${wl:-0},\"daynight\":\"${mode:-}\",\"ev\":${ev:-null},\"track\":$track,\"shbf2tcp\":$rtsp}"
    ;;
*)
    echo "unknown command" >&2; exit 1
    ;;
esac
