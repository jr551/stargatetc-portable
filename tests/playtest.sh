#!/usr/bin/env bash
# Deploy rebuilt SGTC Linux game DLLs and run automated parity + optional Xash smoke.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOD="$ROOT/stargatetc"
PORTABLE="$ROOT/hlsdk-portable"
BUILD="$PORTABLE/build-sgtc"

ensure_mod_tree() {
  if [[ -f "$MOD/liblist.gam" || -f "$MOD/Liblist.gam" ]] && [[ -f "$MOD/maps/ctp_amon.bsp" ]]; then
    [[ -f "$MOD/liblist.gam" ]] || ln -sf Liblist.gam "$MOD/liblist.gam"
    return 0
  fi
  echo "== fetch mod assets (jr551/stargatetc-portable) =="
  local zip="/tmp/sgtc-mod.zip"
  curl -fsSL -o "$zip" "https://github.com/jr551/stargatetc-portable/archive/refs/heads/main.zip"
  rm -rf "$ROOT/stargatetc-portable-main"
  unzip -q "$zip" 'stargatetc-portable-main/stargatetc/*' -d "$ROOT"
  rm -rf "$MOD"
  mv "$ROOT/stargatetc-portable-main/stargatetc" "$MOD"
  rm -rf "$ROOT/stargatetc-portable-main"
  [[ -f "$MOD/liblist.gam" ]] || ln -sf Liblist.gam "$MOD/liblist.gam"
}

ensure_mod_tree

echo "== export parity =="
python3 "$ROOT/tests/test_exports.py"

echo "== logic parity (52 matrix) =="
python3 "$ROOT/tests/test_logic.py"

echo "== client HUD wire spec =="
python3 "$ROOT/tests/test_client_hud.py"

echo "== deploy linux game libs =="
install -D -m 0644 "$BUILD/dlls/hl.so" "$MOD/dlls/hl.so"
install -D -m 0644 "$BUILD/cl_dll/client.so" "$MOD/cl_dlls/client.so"
# Xash reads gamedll_linux; keep metamod path backed up if present.
if grep -q metamod "$MOD/liblist.gam" 2>/dev/null; then
  cp -a "$MOD/liblist.gam" "$MOD/liblist.gam.metamod.bak"
  sed -i 's|^gamedll_linux.*|gamedll_linux "dlls/hl.so"|' "$MOD/liblist.gam"
fi

XASH=""
for cand in \
  "$ROOT/xash3d-fwgs/build/game_launch/xash3d" \
  "/tmp/xash3d-fwgs/build/game_launch/xash3d" \
  "$(command -v xash3d 2>/dev/null || true)"; do
  [[ -n "$cand" && -x "$cand" ]] || continue
  if file "$cand" | grep -q 'ELF 32-bit'; then
    XASH="$cand"
    break
  fi
done

if [[ -z "$XASH" ]]; then
  echo "SKIP: no 32-bit xash3d binary (game DLLs are i386). Install i386 SDL/freetype and build:"
  echo "  cd /tmp/xash3d-fwgs && ./waf configure -T release --32bits && ./waf build"
  exit 0
fi

echo "== xash dedicated smoke (10s) =="
export XASH3D_BASEDIR="$ROOT"
export XASH3D_GAME="stargatetc"
# FWGS uses XASH3D_BASEDIR (not -basedir) for game discovery.
if [[ -f "$MOD/gameinfo.txt" ]]; then
  sed -i 's|^gamedll[[:space:]].*|gamedll\t\t"dlls/hl.dll"|' "$MOD/gameinfo.txt"
  grep -q gamedll_linux "$MOD/gameinfo.txt" || echo 'gamedll_linux\t"dlls/hl.so"' >> "$MOD/gameinfo.txt"
  sed -i 's|^gamedll_linux.*|gamedll_linux\t"dlls/hl.so"|' "$MOD/gameinfo.txt" 2>/dev/null || true
fi
XASH_ROOT="$(cd "$(dirname "$XASH")/.." && pwd)"
XASH_LIBS=""
for d in engine filesystem cl_dll dlls ref/gl ref/soft; do
  [[ -d "$XASH_ROOT/$d" ]] && XASH_LIBS="${XASH_LIBS:+$XASH_LIBS:}$XASH_ROOT/$d"
done
export LD_LIBRARY_PATH="${XASH_LIBS:+$XASH_LIBS:}$(dirname "$XASH"):${LD_LIBRARY_PATH:-}"
timeout 12s "$XASH" -dev 2 -ref soft -game stargatetc -dedicated +maxplayers 4 +map ctp_amon +sv_lan 1 \
  2>&1 | tee "$ROOT/tests/.build/playtest_dedicated.log" | tail -20
echo "playtest log: tests/.build/playtest_dedicated.log"

if [[ -x "$ROOT/tests/playtest_client.sh" ]]; then
  echo "== optional client smoke (non-gating until VGUI API parity) =="
  "$ROOT/tests/playtest_client.sh" || echo "WARN: client smoke failed (see tests/.build/playtest_client.log)"
fi
