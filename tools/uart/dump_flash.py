#!/usr/bin/env python3
"""Dump the 16 MB SPI NOR through U-Boot only (no network, no SD write needed).

Run at the U-Boot prompt first:   sf probe 0; sf read 0x21000000 0 0x1000000
Then: dump_flash.py [--port /dev/ttyUSB0] [--out backup]
Every 64 KB block is read with md.b and verified against U-Boot's crc32; all-0xFF blocks are skipped.
Resumable (blocks/NNN.bin). ~28 s per block → ~1 h 45 min for the whole chip.
"""
import argparse
import os
import re
import sys
import zlib

import serial

from uboot import cmd

BASE = 0x21000000
SIZE = 0x1000000
BLK = 0x10000
FF_CRC = zlib.crc32(b"\xff" * BLK)
LINE = re.compile(r"^([0-9a-f]{8}):((?: [0-9a-f]{2}){1,16})", re.M)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    ap.add_argument("--out", default="backup")
    a = ap.parse_args()
    blocks = os.path.join(a.out, "blocks")
    os.makedirs(blocks, exist_ok=True)
    with serial.Serial(a.port, 115200) as ser:
        for i in range(SIZE // BLK):
            path = os.path.join(blocks, f"{i:03d}.bin")
            if os.path.exists(path):
                continue
            addr = BASE + i * BLK
            crc = int(re.search(r"==> ([0-9a-f]{8})", cmd(ser, f"crc32 {addr:x} {BLK:x}", 20)).group(1), 16)
            if crc == FF_CRC:
                data = b"\xff" * BLK
            else:
                for attempt in range(3):
                    out = cmd(ser, f"md.b {addr:x} {BLK:x}", 120)
                    data, expect = bytearray(), addr
                    for m in LINE.finditer(out):
                        if int(m.group(1), 16) != expect:
                            break
                        chunk = bytes.fromhex(m.group(2).replace(" ", ""))
                        data += chunk
                        expect += len(chunk)
                    data = bytes(data[:BLK])
                    if len(data) == BLK and zlib.crc32(data) == crc:
                        break
                    print(f"block {i:03d} retry {attempt + 1}", flush=True)
                else:
                    sys.exit(f"block {i:03d} failed")
            open(path, "wb").write(data)
            print(f"block {i:03d}/255 crc={crc:08x}", flush=True)
    with open(os.path.join(a.out, "nor16m.bin"), "wb") as f:
        for i in range(SIZE // BLK):
            f.write(open(os.path.join(blocks, f"{i:03d}.bin"), "rb").read())
    print("done:", os.path.join(a.out, "nor16m.bin"))


if __name__ == "__main__":
    main()
