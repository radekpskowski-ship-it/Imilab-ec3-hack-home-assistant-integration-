#!/bin/sh
# Builds everything that goes to /mnt/data/hack on the camera (ARMv7, uClibc, static where possible).
#   ./build.sh            → out/hack/ (ready to pack with ./build.sh pack)
# Needs: wget, tar, make, gcc-style host tools. Downloads the Bootlin toolchain and sources into .cache/.
set -eu
TOP=$(cd "$(dirname "$0")" && pwd)
CACHE=${CACHE:-$TOP/.cache}
OUT=$TOP/out
TC_NAME=armv7-eabihf--uclibc--stable-2018.02-2
TC_URL=https://toolchains.bootlin.com/downloads/releases/toolchains/armv7-eabihf/tarballs/$TC_NAME.tar.bz2
DROPBEAR=dropbear-2024.86
DROPBEAR_URL=https://matt.ucc.asn.au/dropbear/releases/$DROPBEAR.tar.bz2
MOSQ=mosquitto-2.0.20
MOSQ_URL=https://mosquitto.org/files/source/$MOSQ.tar.gz
mkdir -p "$CACHE" "$OUT/hack/bin" "$OUT/hack/lib" "$OUT/stubs"

fetch() { [ -f "$CACHE/$(basename "$1")" ] || wget -q -O "$CACHE/$(basename "$1")" "$1"; }

if [ -z "${TOOLCHAIN:-}" ]; then
    fetch "$TC_URL"
    [ -d "$CACHE/$TC_NAME" ] || tar -C "$CACHE" -xjf "$CACHE/$TC_NAME.tar.bz2"
    TOOLCHAIN=$CACHE/$TC_NAME
fi
export PATH="$TOOLCHAIN/bin:$PATH"
CC=arm-linux-gcc
STRIP=arm-linux-strip

# --- stubs of the vendor libraries (link time only) ---
S=$OUT/stubs
$CC -shared -fPIC -DSTUB_EV -Wl,-soname,libev.so.4 -o $S/libev.so "$TOP/src/stubs.c"
$CC -shared -fPIC -DSTUB_SHBF -Wl,-soname,libshbf.so.0.2 -o $S/libshbf.so "$TOP/src/stubs.c"
$CC -shared -fPIC -DSTUB_SHBFEV -Wl,-soname,libshbfev.so.0.2 -o $S/libshbfev.so "$TOP/src/stubs.c"

# --- our tools ---
for t in shbf2tcp mdprobe shbfprobe shbfdump; do
    $CC -Os -Wall -o "$OUT/hack/bin/$t" "$TOP/src/$t.c" -L$S -lshbfev -lshbf -lev -Wl,--allow-shlib-undefined
    $STRIP "$OUT/hack/bin/$t"
done
$CC -Os -shared -fPIC -o "$OUT/hack/lib/libunbuf.so" "$TOP/src/unbuf.c" && $STRIP "$OUT/hack/lib/libunbuf.so"

# --- dropbear (static multi-binary; host keys and PATH under /mnt/data/hack) ---
fetch "$DROPBEAR_URL"
if [ ! -x "$OUT/hack/bin/dropbearmulti" ]; then
    rm -rf "$CACHE/$DROPBEAR" && tar -C "$CACHE" -xjf "$CACHE/$DROPBEAR.tar.bz2"
    cp "$TOP/src/dropbear-localoptions.h" "$CACHE/$DROPBEAR/localoptions.h"
    (cd "$CACHE/$DROPBEAR" && ./configure --host=arm-linux --disable-zlib --disable-lastlog --disable-utmp \
        --disable-utmpx --disable-wtmp --disable-wtmpx --disable-pututline --disable-pututxline --enable-static \
        CFLAGS="-Os -ffunction-sections -fdata-sections" LDFLAGS=-Wl,--gc-sections >/dev/null &&
     make -j"$(nproc)" PROGRAMS="dropbear dbclient dropbearkey scp" MULTI=1 STATIC=1 >/dev/null)
    $STRIP -o "$OUT/hack/bin/dropbearmulti" "$CACHE/$DROPBEAR/dropbearmulti"
fi

# --- mosquitto_pub / mosquitto_sub (static, no TLS) ---
fetch "$MOSQ_URL"
if [ ! -x "$OUT/hack/bin/mosquitto_pub" ]; then
    rm -rf "$CACHE/$MOSQ" && tar -C "$CACHE" -xzf "$CACHE/$MOSQ.tar.gz"
    (cd "$CACHE/$MOSQ" &&
     make -C lib CC=$CC WITH_TLS=no WITH_CJSON=no WITH_SRV=no WITH_STATIC_LIBRARIES=yes \
         WITH_SHARED_LIBRARIES=no WITH_DOCS=no libmosquitto.a >/dev/null &&
     make -C client CC=$CC WITH_TLS=no WITH_CJSON=no WITH_SRV=no WITH_STATIC_LIBRARIES=yes \
         WITH_SHARED_LIBRARIES=no WITH_DOCS=no CLIENT_LDFLAGS="-static" static_pub static_sub >/dev/null)
    for c in mosquitto_pub mosquitto_sub; do $STRIP -o "$OUT/hack/bin/$c" "$CACHE/$MOSQ/client/$c"; done
fi

# --- scripts ---
cp "$TOP"/hack/*.sh "$OUT/hack/"
cp "$TOP"/hack/bin/*.sh "$OUT/hack/bin/"
mkdir -p "$OUT/hack/etc" "$OUT/hack/root/.ssh"
cp "$TOP"/hack/etc/miio_ota.rc.main "$OUT/hack/etc/"
chmod 755 "$OUT"/hack/*.sh "$OUT"/hack/bin/*

if [ "${1:-}" = pack ]; then
    for f in etc/wifi.conf etc/shadow etc/mqtt.conf root/.ssh/authorized_keys; do
        [ -f "$TOP/hack/$f" ] || { echo "missing hack/$f (copy from hack/$f.example)"; exit 1; }
        cp "$TOP/hack/$f" "$OUT/hack/$f"
    done
    (cd "$OUT" && tar czf hack.tgz hack)
    echo "out/hack.tgz ready ($(wc -c < "$OUT/hack.tgz") bytes)"
fi
echo "built: $(ls "$OUT/hack/bin" | tr '\n' ' ')"
