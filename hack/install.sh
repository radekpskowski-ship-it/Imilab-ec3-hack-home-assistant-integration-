#!/bin/sh
# Installer run from init=/bin/sh (DATA mounted at /mnt/data). Logs to /dev/console.
exec >/dev/console 2>&1
HACK=/mnt/data/hack
W=/mnt/data/bin/wifi_start.sh
echo "hack-install: start"
chmod 755 $HACK/boot.sh $HACK/bin/*
chmod 600 $HACK/etc/shadow $HACK/etc/wifi.conf $HACK/root/.ssh/authorized_keys
chmod 700 $HACK/root/.ssh
[ -f $W.orig ] || cp -p $W $W.orig
if ! grep -q wifi_hook.sh $W; then
    sed -i '/^start \$1/i [ -f /mnt/data/hack/wifi_hook.sh ] \&\& . /mnt/data/hack/wifi_hook.sh' $W
fi
echo "hack-install: hook:"
grep -n -e wifi_hook -e '^start' $W
ls -la $HACK $HACK/bin
sync
echo "hack-install: DONE"
