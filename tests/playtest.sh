#!/usr/bin/env bash
# Deploy rebuilt SGTC Linux game DLLs and run automated parity + optional Xash smoke.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOD="$ROOT/stargatetc"
PORTABLE="$ROOT/hlsdk-portable"
BUILD="$PORTABLE/build-sgtc"

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
export LD_LIBRARY_PATH="$(dirname "$XASH"):${LD_LIBRARY_PATH:-}"
timeout 12s "$XASH" -dev 2 -ref soft -game "$MOD" -dedicated +maxplayers 4 +map ctp_amon +sv_lan 1 \
  2>&1 | tee "$ROOT/tests/.build/playtest_dedicated.log" | tail -20
echo "playtest log: tests/.build/playtest_dedicated.log"
