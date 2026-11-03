#!/usr/bin/env python3
"""Talk to the SigmaStar U-Boot prompt over UART (115200 8N1).

  uboot.py catch              # spam break keys until "SigmaStar # " (power-cycle the camera now)
  uboot.py cmd "printenv"     # run one command at the prompt and print the answer
Port: --port /dev/ttyUSB0 (default).
"""
import argparse
import sys
import time

import serial

PROMPT = b"SigmaStar # "


def catch(ser: serial.Serial, seconds: int = 300) -> None:
    """bootdelay=0, but \\r + Ctrl-C sent continuously while the camera powers on stops autoboot."""
    ser.timeout = 0.05
    buf = b""
    end = time.time() + seconds
    while time.time() < end:
        ser.write(b"\r\x03 ")
        buf += ser.read(4096)
        if PROMPT.rstrip() in buf[-300:]:
            time.sleep(0.5)
            ser.timeout = 0.2
            ser.read(65536)
            return
    sys.exit("no U-Boot prompt")


def cmd(ser: serial.Serial, command: str, timeout: float = 30) -> str:
    ser.timeout = 0.2
    ser.reset_input_buffer()
    ser.write(command.encode() + b"\n")
    buf = b""
    end = time.time() + timeout
    while time.time() < end:
        buf += ser.read(4096)
        if buf.endswith(PROMPT):
            return buf.decode(errors="replace").replace("\r", "")
    raise TimeoutError(command)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ttyUSB0")
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("catch")
    c = sub.add_parser("cmd")
    c.add_argument("command")
    c.add_argument("--timeout", type=float, default=30)
    a = ap.parse_args()
    with serial.Serial(a.port, 115200) as ser:
        if a.action == "catch":
            catch(ser)
            print("U-Boot prompt caught")
        else:
            print(cmd(ser, a.command, a.timeout))


if __name__ == "__main__":
    main()
