#!/bin/sh
# Camera add-ons: root password, SSH keys, dropbear, OTA block. Started from wifi_hook.sh.
HACK=/mnt/data/hack
[ -f $HACK/disable ] && exit 0
echo "hack: boot.sh start"

grep -q " /etc/shadow " /proc/mounts || mount --bind $HACK/etc/shadow /etc/shadow
grep -q " /root " /proc/mounts || mount --bind $HACK/root /root

for p in dropbear dropbearkey scp dbclient; do
    [ -e /tmp/hackbin/$p ] || { mkdir -p /tmp/hackbin; ln -s $HACK/bin/dropbearmulti /tmp/hackbin/$p; }
done
export PATH=/tmp/hackbin:$HACK/bin:$PATH

# the scp server side looks for "scp" in PATH
ln -sf $HACK/bin/dropbearmulti /tmp/hackbin/scp

pidof dropbearmulti >/dev/null || dropbear -R -p 22
echo "hack: dropbear started"

# OTA block (skipped when $HACK/allow_ota exists).
# 1) The perp service miio_ota runs "sleep" instead of miio_ota (see hack/etc/miio_ota.rc.main;
#    the original is kept as rc.main.orig). This runs before S50perp, so it applies on this boot.
# 2) In the background, once perpd is up: kill a miio_ota that may have started anyway, and make
#    /mnt/data/BOOT.bin.gz a directory so uboot_ota.sh never flashes a new U-Boot.
R=/mnt/data/etc/perp/miio_ota/rc.main
if [ ! -f $HACK/allow_ota ] && [ -f $HACK/etc/miio_ota.rc.main ] && ! grep -q "hack:" $R 2>/dev/null; then
    [ -f $R.orig ] || cp -p $R $R.orig
    cp $HACK/etc/miio_ota.rc.main $R && chmod 755 $R
fi
[ -f $HACK/allow_ota ] || (
    for i in $(seq 60); do pidof perpd >/dev/null && break; sleep 2; done
    sleep 5
    killall miio_ota 2>/dev/null
    [ -d /mnt/data/BOOT.bin.gz ] || { rm -f /mnt/data/BOOT.bin.gz /mnt/data/BOOT.md5sum; mkdir /mnt/data/BOOT.bin.gz; }
    echo "hack: OTA blocked"
) >/dev/null 2>&1 &

[ -x $HACK/local.sh ] && $HACK/local.sh &
exit 0
