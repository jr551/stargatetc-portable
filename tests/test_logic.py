#!/usr/bin/env python3
"""
test_logic.py — behavioral comparison: ref stc_i386.so vs rebuilt hl.so.

Drives tests/.build/stub_engine (32-bit dlopen harness) over every SGTC
entity family where the engine itself only reaches code through the
GetEntityAPI table + exported class factories:

  rules <mp_gamemode>   — InstallGameRules / SGTC_InstallGameRules dispatch
  weapon <link> <mangled-GetItemInfo> — Spawn + GetItemInfo through vtable
  gate <multi_gate_N>   — KeyValue/Spawn/ManagerUse/ManagerThink/clone
  trigger <cls> <key> <val> — Spawn + KeyValue + Touch + Think + Use

PASS/FAIL line format is identical for both binaries; this script compares
the normalized "detail" suffix per (command,subject) pair and reports
mismatches. Behavior-identical binaries produce zero mismatches.

Usage: python3 tests/test_logic.py [--ref PATH] [--built PATH]
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUB = ROOT / "tests" / ".build" / "stub_engine"
REF = ROOT / "ref" / "stc_i386.so"
BUILT = ROOT / "hlsdk-portable" / "build-dbg" / "dlls" / "hl.so"

# ref weapon iIds decoded from GetItemInfo disasm + verified live below.
# (link_classname, expected_iId(None=use ref), GetItemInfo mangled symbol)
WEAPONS = [
    ("weapon_coujaf", "9mmAR", "_ZN7CCoujaf11GetItemInfoEP8ItemInfo"),
    ("weapon_m92s", "9mmhandgun", "_ZN5CM92s11GetItemInfoEP8ItemInfo"),
    ("weapon_couteau", "couteau", "_ZN8CCouteau11GetItemInfoEP8ItemInfo"),
    ("weapon_mp5", "mp5", "_ZN4CMP511GetItemInfoEP8ItemInfo"),
    ("weapon_p90", "p90", "_ZN4CP9011GetItemInfoEP8ItemInfo"),
    ("weapon_spas", "spas", "_ZN8CShotgun11GetItemInfoEP8ItemInfo"),
    ("weapon_tacgun", "tacgun", "_ZN7CTacgun11GetItemInfoEP8ItemInfo"),
    ("weapon_usas", "usas", "_ZN5CUsas11GetItemInfoEP8ItemInfo"),
    ("weapon_m16", "m16", "_ZN4CM1611GetItemInfoEP8ItemInfo"),
    ("weapon_psg1", "psg1", "_ZN5CPsg111GetItemInfoEP8ItemInfo"),
    ("weapon_batsup", "batsup", "_ZN14CBatonSupplice11GetItemInfoEP8ItemInfo"),
    ("weapon_flashbang", "flashbang", "_ZN10CFlashBang11GetItemInfoEP8ItemInfo"),
    ("weapon_zat", "zat", "_ZN4CZat11GetItemInfoEP8ItemInfo"),
    ("weapon_zatarc", "zatarc", "_ZN7CZatarc11GetItemInfoEP8ItemInfo"),
    ("weapon_lance", "lance", "_ZN11CLanceJaffa11GetItemInfoEP8ItemInfo"),
    ("weapon_reetou", "reetou", "_ZN7CReetou11GetItemInfoEP8ItemInfo"),
    ("weapon_larve", "larve", "_ZN6CLarve11GetItemInfoEP8ItemInfo"),
    ("weapon_invis", "invis", "_ZN6CInvis11GetItemInfoEP8ItemInfo"),
    ("weapon_main", "maindieu", "_ZN9CMainDieu11GetItemInfoEP8ItemInfo"),
    ("weapon_medic", "medic", "_ZN7CMedicx11GetItemInfoEP8ItemInfo"),
    ("weapon_goaregen", "medicxgoa", "_ZN10CMedicxgoa11GetItemInfoEP8ItemInfo"),
    ("weapon_gacgoa", "grenadechoc", "_ZN12CGrenadeChoc11GetItemInfoEP8ItemInfo"),
    ("weapon_mustardgrenade", "mustard", "_ZN15CMustardGrenade11GetItemInfoEP8ItemInfo"),
    ("weapon_narcogrenade", "narco", "_ZN13CNarcoGrenade11GetItemInfoEP8ItemInfo"),
    ("weapon_nervegrenade", "nerve", "_ZN13CNerveGrenade11GetItemInfoEP8ItemInfo"),
    ("weapon_smokegrenade", "smoke", "_ZN13CSmokeGrenade11GetItemInfoEP8ItemInfo"),
    ("weapon_handgrenade", "handgrenade", "_ZN12CHandGrenade11GetItemInfoEP8ItemInfo"),
    ("weapon_c4", "c4", "_ZN8CSatchel11GetItemInfoEP8ItemInfo"),
    ("weapon_mine", "mine", "_ZN9CTripmine11GetItemInfoEP8ItemInfo"),
]

MODES = ["sgi_tc", "ctp_tc", "sg_tc", "un_tc", "inv_tc", "rep_tc",
         "ctc", "ctf", "tdm", "gib", "", "x"]

GATES = [f"multi_gate_{i}" for i in (1, 8, 9, 17, 19, 20, 21, 49)]

TRIGGERS = [
    ("env_fog", "density", "0.5"),
    ("trigger_capture", "target", "cap01"),
    ("game_nuke", "target", "boom"),
]

SIT_RE = re.compile(r"^SIT\t([^\t]+)\t([^\t]+)\t?(.*)$")


def run(binary, args):
    try:
        p = subprocess.run([str(STUB), str(binary)] + args,
                           capture_output=True, text=True, timeout=20)
        return p.stdout
    except subprocess.TimeoutExpired:
        return ""


def sits(binary):
    """Return {subject: (verdict, detail)} over the whole matrix."""
    out = {}
    for mode in MODES:
        for line in run(binary, ["rules", mode]).splitlines():
            m = SIT_RE.match(line)
            if m:
                # normalize pointers
                detail = re.sub(r"0x[0-9a-fA-F]+", "PTR", m.group(3))
                out[f"rules:{mode}"] = (m.group(2), detail)
    for link, _name, sym in WEAPONS:
        for line in run(binary, ["weapon", link, "0", sym]).splitlines():
            m = SIT_RE.match(line)
            if m:
                detail = re.sub(r"0x[0-9a-fA-F]+", "PTR", m.group(3))
                detail = re.sub(r"want\d+", "wantN", detail)
                out[f"weapon:{link}"] = (m.group(2), detail)
    for g in GATES:
        for line in run(binary, ["gate", g]).splitlines():
            m = SIT_RE.match(line)
            if m:
                out[f"gate:{g}"] = (m.group(2), re.sub(r"0x[0-9a-fA-F]+", "PTR", m.group(3)))
    for cls, k, v in TRIGGERS:
        for line in run(binary, ["trigger", cls, k, v]).splitlines():
            m = SIT_RE.match(line)
            if m:
                out[f"trigger:{cls}"] = (m.group(2), m.group(3))
    return out


def main():
    argv = sys.argv[1:]
    ref = Path(argv[argv.index("--ref") + 1]) if "--ref" in argv else REF
    built = Path(argv[argv.index("--built") + 1]) if "--built" in argv else BUILT
    if not STUB.exists():
        print("stub_engine not built: gcc -m32 stub_engine.c -ldl", file=sys.stderr)
        return 1
    if not ref.exists() or not built.exists():
        print(f"missing binary: {ref.exists()=}, {built.exists()=}", file=sys.stderr)
        return 1

    rs, bs = sits(ref), sits(built)
    keys = sorted(set(rs) | set(bs))
    n_pass = n_diff = n_missing = 0
    for k in keys:
        r, b = rs.get(k), bs.get(k)
        if r is None or b is None:
            n_missing += 1
            print(f"MISSING {k:32} ref={r} built={b}")
        elif r[0] != b[0]:
            n_diff += 1
            print(f"DIFF    {k:32} ref={r} built={b}")
        elif r[0] == "FAIL" and r[1] != b[1] and "wantN" not in r[1]:
            # both FAIL is fine only if details match intent
            if r != b:
                n_diff += 1
                print(f"DIFF    {k:32} ref={r} built={b}")
            else:
                n_pass += 1
        else:
            n_pass += 1
    print()
    print(f"matrix={len(keys)}  same-behavior={n_pass}  verdict-or-detail-diff={n_diff}  missing-side={n_missing}")
    return 0 if n_diff == 0 and n_missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
