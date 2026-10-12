#!/usr/bin/env python3
"""
test_exports.py - StargateTC export-comparison harness.

Compares the dynamic (exported) symbol surface of the original GoldSrc server
plugin against the hlsdk-portable rebuild:

    reference : ref/stc_i386.so                          (StargateTC 2.0, unstripped)
    rebuild   : hlsdk-portable/build-sgtc/dlls/hl.so   (jr551/sgtc1-hlsdk-portable)

Checks
  1. entity factory symbol sets per prefix
     (weapon_*, monster_*, multi_gate_*, info_*, trigger_*, env_*, game_*, func_tank*)
     -> present / missing / extra per side
  2. engine export sanity: GiveFnptrsToDll, GetEntityAPI, GetEntityAPI2,
     GetNewDLLFunctions  (GetEntityAPI is the REQUIRED one)
  3. gmsg* network-message globals (auto-discovered from each binary)
  4. per-factory dlsym load test on both binaries, via a native -m32 helper
     (tests/dlprobe.c).  A symbol present in .dynsym is not necessarily
     resolvable; dlopen+dlsym proves it.

Read-only with respect to both binaries and all repo sources; the only files
this harness writes are inside tests/ (the compiled helper + build scratch).

Usage:
    python3 tests/test_exports.py [--json] [--no-load]

Exit status: 0 if the harness itself ran and the engine-export contract holds,
1 if a required engine export is missing (hard failure), 2 if a binary is
unreadable.  Gaps in the ported entity surface are reported but do NOT fail the
run - the baseline rebuild is known to predate the sgtc_* sources.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BUILD_SCRATCH = os.path.join(HERE, ".build")

REF_SO = os.path.join(ROOT, "ref", "stc_i386.so")
REBUILD_SO = os.path.join(ROOT, os.environ.get("SGTC_TREE", "hlsdk-portable"), "build-sgtc", "dlls", "hl.so")

# Prefixes the port is expected to cover.  Trailing underscore is intentional:
# it keeps e.g. `game_` from swallowing unrelated identifiers.
FACTORY_PREFIXES = [
    "weapon_",
    "monster_",
    "multi_gate_",
    "info_",
    "trigger_",
    "env_",
    "game_",
    "func_tank",
]

# The server DLL's translation-unit manifest.  A source that exists on disk but
# is not listed here is silently dropped from the link, which shows up as an
# undefined vtable/function at dlopen time rather than a build error.
DLL_DIR = os.path.join(ROOT, "hlsdk-portable", "dlls")
CMAKE_LISTS = os.path.join(DLL_DIR, "CMakeLists.txt")
CPP_RE = re.compile(r"^\s*([A-Za-z0-9_]+\.cpp)\s*$", re.M)

# Engine entry points the GoldSrc server looks up with dlsym.  GiveFnptrsToDll
# and GetEntityAPI are the mandatory pair; the rest are conventionally present.
ENGINE_EXPORTS_REQUIRED = ["GiveFnptrsToDll", "GetEntityAPI"]
ENGINE_EXPORTS_OPTIONAL = ["GetEntityAPI2", "GetNewDLLFunctions"]


GMSG_RE = re.compile(r"^gmsg[A-Za-z0-9_]+$")
LINK_RE = re.compile(r"LINK_ENTITY_TO_CLASS\(\s*([A-Za-z0-9_]+)")


def die(msg: str, code: int = 2):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# --------------------------------------------------------------------------
# symbol extraction
# --------------------------------------------------------------------------
def dyn_symbols(path: str) -> dict[str, str]:
    """Map of exported symbol name -> nm type letter, from .dynsym."""
    out = subprocess.run(
        ["nm", "-D", "--defined-only", path],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        die(f"nm failed on {path}: {out.stderr.strip()}")
    syms: dict[str, str] = {}
    for line in out.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        typ, name = parts[-2], parts[-1]
        if typ in ("U", "u"):
            continue
        name = name.split("@")[0]  # drop @@GLIBC style version suffixes
        syms[name] = typ
    return syms


def provenance(path: str) -> dict:
    """Identity of the exact binary analysed: size, mtime, sha256."""
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    st = os.stat(path)
    return {
        "path": os.path.relpath(path, ROOT),
        "size": st.st_size,
        "mtime": int(st.st_mtime),
        "sha256": h.hexdigest(),
    }


def by_prefix(syms: dict[str, str], prefix: str) -> set[str]:
    return {n for n in syms if n.startswith(prefix)}


def gmsg_set(syms: dict[str, str]) -> set[str]:
    return {n for n in syms if GMSG_RE.match(n)}


def sgtc_declared_factories() -> set[str]:
    """Factory names registered by the new sgtc_* sources."""
    found: set[str] = set()
    for fn in sorted(os.listdir(DLL_DIR)):
        if not fn.startswith("sgtc_"):
            continue
        if not fn.endswith((".cpp", ".h")):
            continue
        with open(os.path.join(DLL_DIR, fn), "r", errors="replace") as fh:
            for name in LINK_RE.findall(fh.read()):
                # Macro LINK_ENTITY_TO_CLASS( multi_gate_##N, ...) false-positive.
                if name.startswith("multi_gate_") and not name[11:].isdigit():
                    continue
                found.add(name)
    return found


def build_manifest() -> dict:
    """Which translation units are listed in CMakeLists vs present on disk."""
    with open(CMAKE_LISTS, "r", errors="replace") as fh:
        listed = set(CPP_RE.findall(fh.read()))
    on_disk = {f for f in os.listdir(DLL_DIR) if f.endswith(".cpp")}
    return {
        "listed": len(listed),
        "on_disk": len(on_disk),
        "not_compiled": sorted(on_disk - listed),
        "listed_missing": sorted(listed - on_disk),
    }


# --------------------------------------------------------------------------
# dlsym load test (native 32-bit helper)
# --------------------------------------------------------------------------
def build_dlprobe() -> str | None:
    src = os.path.join(HERE, "dlprobe.c")
    if not os.path.isfile(src):
        return None
    os.makedirs(BUILD_SCRATCH, exist_ok=True)
    exe = os.path.join(BUILD_SCRATCH, "dlprobe")
    if os.path.isfile(exe) and os.path.getmtime(exe) > os.path.getmtime(src):
        return exe
    cc = shutil.which("gcc") or shutil.which("cc")
    if not cc:
        return None
    r = subprocess.run(
        [cc, "-m32", "-O1", "-rdynamic", "-o", exe, src, "-ldl"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f"NOTE: could not build 32-bit dlprobe: {r.stderr.strip()[:200]}")
        return None
    return exe


def load_test(exe: str, so: str, names: list[str]) -> dict:
    """Run dlprobe -> {opened, mode, strict, resolved:{name:bool}, detail}."""
    symfile = os.path.join(BUILD_SCRATCH, "symnames.txt")
    with open(symfile, "w") as fh:
        fh.write("\n".join(names) + "\n")
    r = subprocess.run([exe, so, symfile], capture_output=True, text=True)
    opened, mode, detail, resolved = False, "-", "", {}
    for line in r.stdout.splitlines():
        f = line.split("\t")
        if f[0] == "DLOPEN":
            opened = f[1] == "OK"
            mode = f[2] if len(f) > 2 else "-"
            detail = f[3] if len(f) > 3 else ""
        elif f[0] == "SYM" and len(f) == 3:
            resolved[f[2]] = f[1] == "OK"
    return {
        "opened": opened,
        "mode": mode,
        "strict": mode == "NOW",  # RTLD_NOW == all deps resolved
        "detail": detail,
        "resolved": resolved,
    }


# --------------------------------------------------------------------------
# report helpers
# --------------------------------------------------------------------------
def fmt_set(s: set[str], limit: int = 12) -> str:
    items = sorted(s)
    if len(items) <= limit:
        return ", ".join(items) if items else "-"
    return ", ".join(items[:limit]) + f" ... (+{len(items) - limit} more)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--no-load", action="store_true", help="skip dlopen/dlsym test")
    args = ap.parse_args()

    for p in (REF_SO, REBUILD_SO):
        if not os.path.isfile(p):
            die(f"missing binary: {p}")

    ref = dyn_symbols(REF_SO)
    reb = dyn_symbols(REBUILD_SO)
    declared = sgtc_declared_factories()
    manifest = build_manifest()

    report: dict = {
        "reference": os.path.relpath(REF_SO, ROOT),
        "rebuild": os.path.relpath(REBUILD_SO, ROOT),
        "binaries": {
            "reference": provenance(REF_SO),
            "rebuild": provenance(REBUILD_SO),
        },
        "dynsym_counts": {"reference": len(ref), "rebuild": len(reb)},
        "build_manifest": manifest,
        "engine_exports": {},
        "factories": {},
        "gmsg": {},
        "load_test": {},
        "verdicts": {},
    }

    # ---- 2. engine exports ------------------------------------------------
    for name in ENGINE_EXPORTS_REQUIRED + ENGINE_EXPORTS_OPTIONAL:
        report["engine_exports"][name] = {
            "required": name in ENGINE_EXPORTS_REQUIRED,
            "reference": ref.get(name),
            "rebuild": reb.get(name),
        }
    engine_ok = all(
        report["engine_exports"][n]["rebuild"] for n in ENGINE_EXPORTS_REQUIRED
    )

    # ---- 1. factory sets --------------------------------------------------
    factory_missing_rebuild: set[str] = set()
    for prefix in FACTORY_PREFIXES:
        rs, bs = by_prefix(ref, prefix), by_prefix(reb, prefix)
        missing = rs - bs            # in original, absent from rebuild
        extra = bs - rs              # new in rebuild
        factory_missing_rebuild |= missing
        report["factories"][prefix] = {
            "reference": len(rs),
            "rebuild": len(bs),
            "missing_in_rebuild": sorted(missing),
            "extra_in_rebuild": sorted(extra),
        }

    # ---- 3. gmsg ----------------------------------------------------------
    rg, bg = gmsg_set(ref), gmsg_set(reb)
    report["gmsg"] = {
        "reference": sorted(rg),
        "rebuild": sorted(bg),
        "missing_in_rebuild": sorted(rg - bg),
        "extra_in_rebuild": sorted(bg - rg),
    }

    # ---- 4. load test -----------------------------------------------------
    probe_names = (
        ENGINE_EXPORTS_REQUIRED
        + ENGINE_EXPORTS_OPTIONAL
        + sorted(declared)
        + ["gmsgDeathMsg"]
    )
    # de-dup, keep order
    probe_names = list(dict.fromkeys(probe_names))
    load_exe = None if args.no_load else build_dlprobe()
    if load_exe:
        report["load_test"] = {
            "helper": os.path.relpath(load_exe, ROOT),
            "reference": load_test(load_exe, REF_SO, probe_names),
            "rebuild": load_test(load_exe, REBUILD_SO, probe_names),
        }
    else:
        report["load_test"] = {"helper": None, "skipped": True}

    # ---- verdicts ---------------------------------------------------------
    # Missing = absent from the rebuild's .dynsym.  When the load test ran and
    # the library actually opened, use dlsym results (stronger: proves the
    # dynamic linker resolves the symbol).  If dlopen failed, every dlsym would
    # be a false negative, so fall back to .dynsym membership.
    load_ok = report["load_test"].get("rebuild", {}).get("opened", False)
    if load_exe and load_ok:
        lt_reb = report["load_test"]["rebuild"]["resolved"]
        declared_missing = sorted(n for n in declared if not lt_reb.get(n, False))
    else:
        declared_missing = sorted(
            n for n in declared if n not in reb and not n.startswith("multi_gate_")
        )
    lt_rebuild = report["load_test"].get("rebuild", {})
    report["verdicts"] = {
        "engine_exports_ok": engine_ok,
        "rebuild_dlopen_ok": lt_rebuild.get("opened", None),
        "rebuild_dlopen_mode": lt_rebuild.get("mode", None),
        "rebuild_dlopen_strict": lt_rebuild.get("strict", None),
        "rebuild_dlopen_error": lt_rebuild.get("detail", "") if not lt_rebuild.get("opened") else "",
        "sources_not_compiled": manifest["not_compiled"],
        "sgtc_declared_factory_count": len(declared),
        "sgtc_declared_missing_count": len(declared_missing),
        "missing_basis": "dlsym" if (load_exe and load_ok) else "dynsym",
        "sgtc_declared_missing_from_rebuild": declared_missing,
        "factory_prefix_missing_count": len(factory_missing_rebuild),
        "gmsg_missing_count": len(rg - bg),
        "gmsg_extra_count": len(bg - rg),
    }

    # ---- output -----------------------------------------------------------
    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if engine_ok else 1

    def row(cells, widths):
        return "  ".join(str(c).ljust(w) for c, w in zip(cells, widths))

    print("=" * 78)
    print("StargateTC export-comparison harness")
    print("=" * 78)
    import datetime

    def stamp(prov):
        ts = datetime.datetime.fromtimestamp(prov["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
        return f"{prov['size']} B, mtime {ts}, sha256 {prov['sha256'][:16]}"

    print(f"  reference : {report['reference']}   ({len(ref)} exported symbols)")
    print(f"              {stamp(report['binaries']['reference'])}")
    print(f"  rebuild   : {report['rebuild']}   ({len(reb)} exported symbols)")
    print(f"              {stamp(report['binaries']['rebuild'])}")
    print()

    mf = report["build_manifest"]
    print("-" * 78)
    print("0. BUILD MANIFEST (dlls/CMakeLists.txt vs dlls/*.cpp on disk)")
    print("-" * 78)
    print(f"  listed in CMakeLists: {mf['listed']}   .cpp on disk: {mf['on_disk']}")
    if mf["not_compiled"]:
        print(f"  NOT COMPILED ({len(mf['not_compiled'])}): {fmt_set(set(mf['not_compiled']), 10)}")
    else:
        print("  NOT COMPILED: none - every source on disk is linked")
    if mf["listed_missing"]:
        print(f"  LISTED BUT ABSENT ({len(mf['listed_missing'])}): {fmt_set(set(mf['listed_missing']), 10)}")
    print()

    print("-" * 78)
    print("2. ENGINE EXPORTS")
    print("-" * 78)
    w = [26, 9, 10, 10]
    print(row(["symbol", "required", "reference", "rebuild"], w))
    for name, d in report["engine_exports"].items():
        print(
            row(
                [
                    name,
                    "yes" if d["required"] else "no",
                    d["reference"] or "MISSING",
                    d["rebuild"] or "MISSING",
                ],
                w,
            )
        )
    print(f"  -> engine export contract: {'PASS' if engine_ok else 'FAIL'}")
    print()

    print("-" * 78)
    print("1. ENTITY FACTORY SYMBOL SETS")
    print("-" * 78)
    w = [14, 10, 9, 9, 8]
    print(row(["prefix", "reference", "rebuild", "missing", "extra"], w))
    for prefix, d in report["factories"].items():
        print(
            row(
                [
                    prefix,
                    d["reference"],
                    d["rebuild"],
                    len(d["missing_in_rebuild"]),
                    len(d["extra_in_rebuild"]),
                ],
                w,
            )
        )
    print()
    for prefix, d in report["factories"].items():
        if d["missing_in_rebuild"] or d["extra_in_rebuild"]:
            print(f"  {prefix}")
            if d["missing_in_rebuild"]:
                print(f"    missing in rebuild: {fmt_set(set(d['missing_in_rebuild']), 8)}")
            if d["extra_in_rebuild"]:
                print(f"    extra in rebuild  : {fmt_set(set(d['extra_in_rebuild']), 8)}")
    print()

    print("-" * 78)
    print("3. gmsg* MESSAGE VARIABLES")
    print("-" * 78)
    print(f"  reference: {len(rg)}   rebuild: {len(bg)}")
    print(f"  missing in rebuild: {fmt_set(rg - bg, 10)}")
    print(f"  extra in rebuild  : {fmt_set(bg - rg, 10)}")
    print()

    print("-" * 78)
    print("4. PER-FACTORY dlsym LOAD TEST")
    print("-" * 78)
    if not load_exe:
        print("  SKIPPED (no 32-bit dlprobe helper)")
    else:
        for side in ("reference", "rebuild"):
            d = report["load_test"][side]
            state = "OK" if d["opened"] else "FAIL"
            print(f"  {side}: dlopen {state} (RTLD_{d['mode']})")
            if not d["opened"]:
                print(f"    detail: {d['detail']}")
        lt = report["load_test"]["rebuild"]["resolved"]
        ok = sorted(n for n, v in lt.items() if v)
        miss = sorted(n for n, v in lt.items() if not v)
        print(f"  rebuild dlsym OK ({len(ok)}): {fmt_set(set(ok), 10)}")
        print(f"  rebuild dlsym MISSING ({len(miss)}): {fmt_set(set(miss), 14)}")
    print()

    print("-" * 78)
    print("COVERAGE / VERDICT")
    print("-" * 78)
    v = report["verdicts"]
    print(f"  engine exports (required pair)      : {'PASS' if v['engine_exports_ok'] else 'FAIL'}")
    if v["rebuild_dlopen_ok"] is None:
        print("  rebuild dlopen                      : SKIPPED (--no-load)")
    else:
        print(f"  rebuild dlopen                      : {v['rebuild_dlopen_ok']} (RTLD_{v['rebuild_dlopen_mode']})")
        if not v["rebuild_dlopen_ok"]:
            print(f"    -> rebuild cannot be loaded at all: {v['rebuild_dlopen_error'][:100]}")
        elif not v["rebuild_dlopen_strict"]:
            print("  NOTE: rebuild loads only lazily - an undefined symbol remains:")
            print(f"        {report['load_test']['rebuild']['detail'][:110]}")
    if v["sources_not_compiled"]:
        print(f"  sources on disk but NOT compiled     : {len(v['sources_not_compiled'])} "
              f"({fmt_set(set(v['sources_not_compiled']), 8)})")
    print(
        f"  sgtc_* declared factories           : {v['sgtc_declared_factory_count']} "
        f"({v['sgtc_declared_missing_count']} missing, via {v['missing_basis']})"
    )
    print(f"  factory symbols missing from rebuild: {v['factory_prefix_missing_count']}")
    print(f"  gmsg symbols missing from rebuild   : {v['gmsg_missing_count']}")
    print()
    if v["sgtc_declared_missing_from_rebuild"]:
        print("  GAPS: factories declared by sgtc_* sources but not resolvable in the")
        print("        rebuild binary. These are the concrete port items still open:")
        print(f"        {fmt_set(set(v['sgtc_declared_missing_from_rebuild']), 16)}")
        print()

    return 0 if engine_ok else 1


if __name__ == "__main__":
    sys.exit(main())
