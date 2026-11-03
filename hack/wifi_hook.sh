# Sourced from /mnt/data/bin/wifi_start.sh right before "start $1".
HACK=/mnt/data/hack
if [ -f $HACK/etc/wifi.conf ]; then
    get_ssid_passwd()
    {
        . $HACK/etc/wifi.conf
        echo $ssid
        echo $key_mgmt
    }
    # Several networks: ssid/passwd (priority 10), ssid2/passwd2 (9), ssid3/passwd3 (8)...
    # An empty passwd means an open network.
    update_wpa_conf()
    {
        . $HACK/etc/wifi.conf
        {
        echo "ctrl_interface=/var/run/wpa_supplicant"
        echo "update_config=1"
        i=1; prio=10
        while :; do
            if [ $i = 1 ]; then s=$ssid; p=$passwd; else eval s=\$ssid$i; eval p=\$passwd$i; fi
            [ -n "$s" ] || break
            echo "network={"
            echo "        ssid=\"$s\""
            if [ -z "$p" ]; then
                echo "        key_mgmt=NONE"
            else
                echo "        psk=\"$p\""
                echo "        key_mgmt=WPA-PSK"
                echo "    proto=WPA WPA2"
            fi
            echo "    scan_ssid=1"
            echo "    priority=$prio"
            echo "}"
            i=$((i+1)); prio=$((prio-1))
        done
        } > $WPA_SUPPLICANT_CONFIG_FILE
    }
    # Always station mode — also after a factory reset, when bind_status in nvram is empty
    # (no pairing hotspot; the camera rejoins the networks from wifi.conf).
    set -- ENTER_STA_MODEL
fi
[ -x $HACK/boot.sh ] && $HACK/boot.sh >/dev/console 2>&1 &
