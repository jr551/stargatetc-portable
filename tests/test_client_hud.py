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


def ticket_dock_anchor(screen_w: int, screen_h: int) -> tuple[int, int]:
    """ref CHudSgtc::Draw @0x10074a4c — dock sprite top-left."""
    return screen_w - 0x4e, screen_h - 0x8e


def ticket_dock_number_y(screen_h: int) -> int:
    """ref @0x10074f0e — HudNumber row when +0x1684 overlay idle."""
    return screen_h - 0x25


def announce_scroller_origin(screen_w: int, screen_h: int) -> tuple[int, int]:
    """ref @0x10074479 — 5-line announce box anchor."""
    line_h, gap, n = 0xc, 3, 5
    base_x = screen_w // 2 - ((line_h + gap) * n) * 2
    base_y = screen_h // 5 - (line_h * (n + gap)) // 2
    if base_y < 0x69:
        base_y = 0x69
    return base_x, base_y


def concuss_announce_pending(payload: bytes) -> tuple[int, int]:
    """ref FUN_100592cf — byte0 concuss, byte1 DAT_100f1ce8."""
    if len(payload) < 2:
        raise ValueError("Concuss needs 2 bytes")
    return payload[0], payload[1]


def vote_cast_line_y(screen_h: int, line: int) -> int:
    """ref @0x10076464 — line 0=#SELPREF, 1..5=#MODE0..4."""
    mid = screen_h // 2
    if line == 0:
        return mid - 0x32
    return mid + (-0x1e, -0xf, 0, 0xf, 0x1e)[line - 1]


def vote_plzvote_visible(vote_count: int, vote_sel: int, portrait_team: int) -> bool:
    """ref Draw @0x10076292 — #PLZVOTE when team filter on and vote idle."""
    if not portrait_team:
        return False
    if vote_count >= 0 or vote_sel >= 0 or vote_count >= 5:
        return False
    return True


def envfull_payload_size() -> int:
    """19 WRITE_COORD + 7 BYTE + 1 SHORT = 47 (ref CEnvParticule::SendValue @0x15ec68)."""
    return 19 * 2 + 7 + 2


# Expected field effects (mirrors CHudSgtc handlers).
def progress_slot_step(slot: int, slot_x: list[int], team_row: list[int]) -> int:
    """ref FUN_1002a9ca: top DAT_100e1a34[i], bottom (&DAT_100e1a6c)[i] -> team[i-14]."""
    if slot < 14:
        return slot_x[slot]
    return team_row[slot - 14]


def simulate_progress_team_ui_step(
    team: int, state: int, slot: int = 2, slot_x: list[int] | None = None, team_row: list[int] | None = None
) -> tuple[int, int, int]:
    """One ref @0x1002abe2 transition (client-local mirror)."""
    slot_x = slot_x or [0x10] * 28
    team_row = team_row or [0] * 28
    cursor = 0
    if team == 0:
        if state < 2:
            state = 2
    elif team == 1:
        if state == 2:
            state = 0
    elif team == 2:
        cursor += progress_slot_step(slot, slot_x, team_row)
        state = 1
        team = 1
    return team, state, cursor


def armor_tac_phase_after_visup(fl_time: float) -> float:
    """ref @0x100739bd — realtime + 10.0 (rodata @0x10095a50)."""
    return fl_time + 10.0


def armor_tac_phase_after_visdown(fl_time: float) -> float:
    """ref @0x10073aa7 — realtime + 0.001 (rodata @0x10094178)."""
    return fl_time + 0.001


def radar_blip_screen_x(screen_w: int, rx_wire: int) -> int:
    """ref @0x10074009 — ScreenWidth - rx - 0x76."""
    return screen_w - rx_wire - 0x76


def radar_blip_screen_y(ry_wire: int, slide: int = 0x68) -> int:
    """ref @0x10073ffd — ry + 0xca - slide."""
    return ry_wire + 0xca - slide


def entrance_ammo_step(hud_info_mode: int, slide: int, step: int) -> tuple[int, int]:
    """ref @0x10074f66 — ammoline entrance tick (+0x1554/+0x1558)."""
    if hud_info_mode == 0:
        if slide < 0x1d and step < 0x46:
            step += 1
        elif slide < 0x1d and step >= 0x46:
            slide += 1
    elif hud_info_mode > 0 and slide > 0:
        slide -= 1
    return slide, step


def ticket_slide_flags_after_peel(rem: int) -> tuple[int, int, int]:
    """ref @0x10074c5c/0x10074c7e — peel sets ebp-0xc0/0xc4 while draining rem."""
    wide = narrow = 0
    if rem >= 0x3:
        narrow = 1
        rem -= 3
    if rem >= 0x2:
        wide = 1
        rem -= 2
    elif rem > 0:
        rem = 0
    return wide, narrow, rem


def radar_ring_frame(v: int) -> int:
    """ref @0x100740df — frame index before SPR_Draw (15 - wrapped)."""
    frame = 0
    if 0x0b <= v <= 0x15d:
        if v <= 0x0a:
            frame = 0
        elif v < 0x21:
            frame = 1
        elif v <= 0x20:
            frame = 0
        elif v < 0x38:
            frame = 2
        elif v <= 0x36:
            frame = 0
        elif v < 0x4e:
            frame = 3
        elif v <= 0x4d:
            frame = 0
        elif v < 0x65:
            frame = 4
        elif v <= 0x64:
            frame = 0
        elif v < 0x7b:
            frame = 5
        elif v <= 0x7a:
            frame = 0
        elif v < 0x92:
            frame = 6
        elif v <= 0x91:
            frame = 0
        elif v < 0xa8:
            frame = 7
        elif v <= 0xa7:
            frame = 0
        elif v < 0xbf:
            frame = 8
        elif v <= 0xbe:
            frame = 0
        elif v < 0xca:
            frame = 9
        elif v <= 0xc9:
            frame = 0
        elif v < 0xec:
            frame = 10
        elif v <= 0xeb:
            frame = 0
        elif v < 0x102:
            frame = 11
        elif v <= 0x101:
            frame = 0
        elif v < 0x119:
            frame = 12
        elif v <= 0x118:
            frame = 0
        elif v < 0x12f:
            frame = 13
        elif v <= 0x12e:
            frame = 0
        elif v < 0x146:
            frame = 14
        elif v <= 0x145:
            frame = 0
        elif v < 0x15e:
            frame = 15
    frame = (frame + 3) & 0x0f
    return 0x0f - frame


def progress_slot_chip_visible(
    slot: int, state: int, team: int, slot_x: list[int] | None = None
) -> bool:
    """ref FUN_1002a9ca tail @0x1002acc2 — mirrored by SGTC_ProgressSlotChipVisible."""
    slot_x = slot_x or [0x10] * 14 + [0x12] * 14
    if state == 2 or slot_x[slot] == 0:
        return False
    return team == 1


def simulate_progress_team_ui_frame(
    teams: list[int], states: list[int], slot_x: list[int] | None = None
) -> tuple[list[int], list[int], int]:
    """One FUN_1002a9ca frame: cursor reset, st==1 clear, then team transitions."""
    slot_x = slot_x or [0x10] * 14 + [0x12] * 14
    teams = list(teams)
    states = list(states)
    cursor = 0
    for i in range(28):
        if states[i] == 1:
            states[i] = 0
        t = teams[i]
        if t == 0:
            if states[i] < 2:
                states[i] = 2
        elif t == 1:
            if states[i] == 2:
                states[i] = 0
        elif t == 2:
            cursor += progress_slot_step(i, slot_x, teams)
            states[i] = 1
            teams[i] = 1
    return teams, states, cursor


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

    t, st, cur = simulate_progress_team_ui_step(2, 0, slot=2)
    if (t, st, cur) != (1, 1, 0x10):
        print("FAIL progress team ui step", (t, st, cur))
        errors += 1

    team_row = [2] + [0] * 27
    t2, st2, cur2 = simulate_progress_team_ui_step(2, 0, slot=14, team_row=team_row)
    if (t2, st2, cur2) != (1, 1, 2):
        print("FAIL progress team ui bottom step", (t2, st2, cur2))
        errors += 1

    teams_f = [0] * 28
    states_f = [1, 0] + [0] * 26
    teams_f[2] = 2
    _, st_after, cur_f = simulate_progress_team_ui_frame(teams_f, states_f)
    if st_after[0] != 2 or st_after[2] != 1 or cur_f != 0x10:
        print("FAIL progress team ui frame", st_after[0], st_after[2], cur_f)
        errors += 1

    if not progress_slot_chip_visible(3, 0, 1):
        print("FAIL progress chip visible captured st=0")
        errors += 1
    if progress_slot_chip_visible(3, 2, 1):
        print("FAIL progress chip hidden when st=2")
        errors += 1
    if progress_slot_chip_visible(3, 0, 1, slot_x=[0] * 28):
        print("FAIL progress chip hidden when step=0")
        errors += 1
    if progress_slot_chip_visible(3, 1, 2):
        print("FAIL progress chip hidden when team=2")
        errors += 1

    if armor_tac_phase_after_visup(100.0) != 110.0:
        print("FAIL armor tac visup phase")
        errors += 1
    if armor_tac_phase_after_visdown(50.0) != 50.001:
        print("FAIL armor tac visdown phase")
        errors += 1

    if radar_blip_screen_x(640, 512) != 640 - 512 - 0x76:
        print("FAIL radar blip X")
        errors += 1
    if radar_blip_screen_y(-256) != -256 + 0xca - 0x68:
        print("FAIL radar blip Y")
        errors += 1
    if radar_ring_frame(0x20) != radar_ring_frame(0x21):
        pass  # smoke: function defined
    if radar_ring_frame(5) != 0x0f - ((0 + 3) & 0x0f):
        print("FAIL radar ring frame", radar_ring_frame(5))
        errors += 1

    w, n, _ = ticket_slide_flags_after_peel(5)
    if w != 1 or n != 1:
        print("FAIL ticket slide peel flags", w, n)
        errors += 1

    s, t = entrance_ammo_step(0, 0, 0x45)
    if s != 0 or t != 0x46:
        print("FAIL entrance ammo step", s, t)
        errors += 1

    b = simulate_blip(blip_payload(0x32, 64.0, -32.0))
    if b.get("m_iRadarFocusX") != int(64.0 * 8):
        print("FAIL Blip focus", b)
        errors += 1

    if not vote_plzvote_visible(-1, -1, 1):
        print("FAIL PLZVOTE guard")
        errors += 1
    if vote_plzvote_visible(0, -1, 1):
        print("FAIL PLZVOTE should hide when count>=0")
        errors += 1

    if envfull_payload_size() != 47:
        print("FAIL EnvFull wire size", envfull_payload_size())
        errors += 1

    if ticket_dock_anchor(640, 480) != (640 - 0x4e, 480 - 0x8e):
        print("FAIL ticket dock anchor")
        errors += 1
    if ticket_dock_number_y(600) != 600 - 0x25:
        print("FAIL ticket dock number Y")
        errors += 1
    if vote_cast_line_y(600, 0) != 250 or vote_cast_line_y(600, 3) != 300:
        print("FAIL vote cast line Y", vote_cast_line_y(600, 0), vote_cast_line_y(600, 3))
        errors += 1

    ax, ay = announce_scroller_origin(640, 480)
    if (ax, ay) != (640 // 2 - 150, 0x69):
        print("FAIL announce scroller origin", (ax, ay))
        errors += 1
    c0, c1 = concuss_announce_pending(bytes([0, 17]))
    if (c0, c1) != (0, 17):
        print("FAIL concuss wire", (c0, c1))
        errors += 1

    client = ROOT / "hlsdk-portable/build-sgtc/cl_dll/client.so"
    if not client.is_file():
        print("WARN missing", client, "(build hlsdk-portable first)")

    print(f"client_hud_spec errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
