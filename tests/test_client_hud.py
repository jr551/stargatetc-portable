#!/usr/bin/env python3
"""SGTC client HUD usermsg layout checks (ref client.dll REA @0x10076*).

Validates wire formats against our port's documented parsers in sgtc_hud.cpp.
Does not load client.so (no engine); use alongside test_exports + playtest.sh.
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def coord_bytes(v: float) -> bytes:
    """GoldSrc short coord encoding used by READ_COORD (stub: int16 scaled)."""
    return struct.pack("<h", int(v * 8.0))


def progress_payload(cmd: int, icon: int, teams: list[int], tail: int) -> bytes:
    assert len(teams) == 28
    return bytes([cmd & 0xff, icon & 0xff] + [t & 0xff for t in teams] + [tail & 0xff])


def blip_payload(typ: int, x: float, y: float) -> bytes:
    return bytes([typ & 0xff]) + coord_bytes(x) + coord_bytes(y)


def armor_payload(a: int, b: int, sub: int, d: int) -> bytes:
    return bytes([a & 0xff, b & 0xff, sub & 0xff, d & 0xff])


def haskey_payload(mode: int, vote: int) -> bytes:
    return bytes([mode & 0xff, vote & 0xff])


# Expected field effects (mirrors CHudSgtc handlers).
def simulate_progress(buf: bytes) -> dict:
    if len(buf) < 31:
        raise ValueError("Progress needs 31 bytes")
    cmd, icon = buf[0], buf[1]
    teams = list(buf[2:30])
    tail = buf[30]
    blip_prog = 100 if cmd == 100 else (0 if cmd == 0 else None)
    return {
        "m_iProgress": cmd,
        "m_iProgressIcon": icon,
        "m_iProgressTeam": teams,
        "m_iProgressEnd": tail,
        "m_iBlipProgress": blip_prog,
    }


def simulate_blip(buf: bytes) -> dict:
    if len(buf) < 5:
        raise ValueError("Blip needs type + 2 coords")
    typ = buf[0]
    x = struct.unpack("<h", buf[1:3])[0]
    y = struct.unpack("<h", buf[3:5])[0]
    out: dict = {}
    if typ == 0x32:
        out["m_iRadarFocusX"], out["m_iRadarFocusY"] = x, y
    elif typ == 0x3d:
        out["m_iRadarFocusX"], out["m_iRadarFocusY"] = 0, 0
    else:
        out["radar_slot"] = (typ, x, y)
    return out


def main() -> int:
    errors = 0

    p = simulate_progress(progress_payload(100, 2, [1] * 28, 9))
    if p["m_iBlipProgress"] != 100 or p["m_iProgress"] != 100:
        print("FAIL Progress cmd 100", p)
        errors += 1

    p0 = simulate_progress(progress_payload(0, 0, [0] * 28, 0))
    if p0["m_iBlipProgress"] != 0:
        print("FAIL Progress cmd 0", p0)
        errors += 1

    b = simulate_blip(blip_payload(0x32, 64.0, -32.0))
    if b.get("m_iRadarFocusX") != int(64.0 * 8):
        print("FAIL Blip focus", b)
        errors += 1

    client = ROOT / "hlsdk-portable/build-sgtc/cl_dll/client.so"
    if not client.is_file():
        print("WARN missing", client, "(build hlsdk-portable first)")

    print(f"client_hud_spec errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
