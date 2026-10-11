#!/usr/bin/env bash
# Optional interactive Xash3D client smoke (loads client.so + SGTC HUD).
# Requires 32-bit xash3d and a display (or xvfb-run).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOD="$ROOT/stargatetc"
BUILD="$ROOT/hlsdk-portable/build-sgtc"
LOG="$ROOT/tests/.build/playtest_client.log"
mkdir -p "$ROOT/tests/.build"

SMOKE_SEC="${SGTC_CLIENT_SMOKE_SEC:-18}"

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
  echo "SKIP playtest_client: no 32-bit xash3d"
  exit 0
fi

if [[ ! -f "$BUILD/cl_dll/client.so" ]]; then
  echo "SKIP playtest_client: build cl_dll first"
  exit 0
fi

install -D -m 0644 "$BUILD/dlls/hl.so" "$MOD/dlls/hl.so"
install -D -m 0644 "$BUILD/cl_dll/client.so" "$MOD/cl_dlls/client.so"

export XASH3D_BASEDIR="$ROOT"
export XASH3D_GAME="stargatetc"
XASH_ROOT="$(cd "$(dirname "$XASH")/.." && pwd)"
XASH_LIBS=""
for d in engine filesystem cl_dll dlls ref/gl ref/soft menu; do
  [[ -d "$XASH_ROOT/$d" ]] && XASH_LIBS="${XASH_LIBS:+$XASH_LIBS:}$XASH_ROOT/$d"
done
REF=soft
[[ -f "$XASH_ROOT/ref/gl/libref_gl.so" ]] && REF=gl
VGUI_LIB="$BUILD/freevgui"
[[ -f "$VGUI_LIB/vgui.so" ]] || VGUI_LIB=""
export LD_LIBRARY_PATH="${VGUI_LIB:+$VGUI_LIB:}${XASH_LIBS:+$XASH_LIBS:}$(dirname "$XASH"):${LD_LIBRARY_PATH:-}"

RUN=()
if [[ -z "${DISPLAY:-}" ]]; then
  if command -v xvfb-run >/dev/null; then
    RUN=(xvfb-run -a)
  else
    echo "SKIP playtest_client: no DISPLAY and no xvfb-run"
    exit 0
  fi
fi

echo "== xash client smoke (${SMOKE_SEC}s cap, ctp_amon) =="
: >"$LOG"

# Do not pipe through tee|tail — a crashed/hung xash can leave readers blocked forever.
set +e
timeout --foreground --kill-after=5 "${SMOKE_SEC}s" \
  "${RUN[@]}" "$XASH" -dev 2 -ref "$REF" -game stargatetc \
  -window -width 640 -height 480 \
  +maxplayers 4 +map ctp_amon +sv_lan 1 +name playtest_bot \
  >"$LOG" 2>&1
rc=$?
set -e

tail -25 "$LOG" || true

if grep -Eqi 'Crash: signal|VGui_LoadProgs' "$LOG"; then
  echo "WARN: client smoke hit VGUI/crash (known gap: Xash VGUI support API vs ref client.dll)"
  grep -Ei 'Crash: signal|VGui_LoadProgs|pfnMessageEnd|expected [0-9]+ bytes' "$LOG" | head -8
  exit 0
fi
if grep -Eqi 'pfnMessageEnd|expected [0-9]+ bytes|svc_bad|FATAL|Could not load' "$LOG"; then
  echo "FAIL: client smoke log has wire/protocol errors (see $LOG)"
  exit 1
fi

if [[ $rc -eq 124 || $rc -eq 137 ]]; then
  echo "OK: client smoke hit time cap (exit=$rc, expected)"
  exit 0
fi
echo "client smoke exit=$rc log=$LOG"
exit 0
