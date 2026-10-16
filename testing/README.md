# StargateTC Visual A/B Testing Methodology

Notes on how we run the Windows reference build and the Linux port side-by-side on a headless box for visual parity work, plus the goal-loop workflow notes. Everything here was learned the hard way — read before touching the harness.

## 0. The control tool

`testing/sgtc-vnc` wraps the whole verified input + launch recipe into one command. Prefer it over hand-rolled vncdotool/xdotool lines:

```bash
testing/sgtc-vnc status            # process + log tail + fresh capture
testing/sgtc-vnc launch port|orig  # setsid-launch a build (one at a time)
testing/sgtc-vnc kill              # kill whichever build is on :78
testing/sgtc-vnc cap name          # -> /tmp/xashrun/name.png + name_s.png (62%)
testing/sgtc-vnc click RX RY       # real-pixel VGUI click (press/release)
testing/sgtc-vnc sclick SX SY      # click using 62%-capture coords (auto x1.613)
testing/sgtc-vnc console 'classe 1 1'   # open console, run cmd, close
testing/sgtc-vnc join              # menu10 Ok -> classe 1 1 -> kill -> menu 11
```

Known-good click points (real px): menu-10 Ok `(461,706)`; menu-11 Auto Team `(465,739)`; menu-60 Apply `(330,668)`; menu-60 PACK cells `(190,167 + row*22)`.

## 1. The VNC harness

Both builds render into one virtual display so captures are directly comparable.

```bash
# One-time: virtual X display + window manager + VNC server on it
Xvnc :78 -geometry 1024x768 -depth 24 -rfbport 5978 -localhost &
DISPLAY=:78 openbox &          # any trivial WM; needed so the game gets a real window
```

Drive it with `vncdotool` over the RFB socket:

```bash
V=~/.local/bin/vncdotool
S=127.0.0.1::5978
$V -s $S capture out.png        # framebuffer screenshot (full res 1024x768)
$V -s $S key '`'                # toggle console
$V -s $S type 'classe 1 1'      # type text (only inside console)
$V -s $S key enter
$V -s $S move 484 702; $V -s $S click 1
$V -s $S down 1; sleep 0.4; $V -s $S up 1   # explicit press/release when plain click fails
convert out.png -resize 62% out_s.png       # downscale before viewing
```

Coordinate map: captures are 1024x768; when viewing a 62% downscale (635x476) multiply screen coords by ~1.61 to get real pixels. Always verify button coords by cropping the full-res PNG (`convert full.png -crop WxH+X+Y`).

## 2. Launching each build

Scripts live in `testing/run/` (`runport.sh`, `runorig.sh` — edit `name` per run). Both MUST be launched detached or they die instantly:

```bash
setsid testing/run/runport.sh </dev/null >/dev/null 2>&1 &
setsid testing/run/runorig.sh </dev/null >/dev/null 2>&1 &   # wine build
```

**Traps:**
- `nohup ... &` and the agent `name=`+`pty:true` service launch both die silently or instantly. `setsid` + `< /dev/null` is what works.
- `tee` inside a supervised-service bash call produces no log file; redirect inside the script instead.
- Only ONE game at a time per display — kill before switching (`pkill -f xash3d`).

### Port (`runport.sh`)
Runs `/tmp/xash3d-fwgs/build/game_launch/xash3d` with `LD_LIBRARY_PATH` covering `hlsdk-portable/build-sgtc/freevgui` + the fwgs engine/ref_gl/filesystem dirs, `XASH3D_BASEDIR` = repo root, `-game stargatetc -window -width 1024 -height 768 +sv_lan 1 +map ctp_amon`.

### Orig (`runorig.sh`)
`wine xash3d.exe -game stargatetc -dev 2 -log -ref gl +sv_lan 1 +map ctp_amon` in `/home/john/src/StargateTC/project/stargatetc-portable-main` with `WINEPREFIX=/tmp/xashrun/prefix`, `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe`.

## 3. The metamod modal trap (check first if +map doesn't fire)

`git checkout -- stargatetc/` (which we run after every playtest) restores the stock `gameinfo.txt` whose `gamedll` points at `addons/metamod/dlls/metamod.dll` and **drops** the `gamedll_linux` line. Symptom: a modal "can't initialize metamod.so" that blocks `+map` and every `map` command, and eats clicks.

Fix before launching the port:

```bash
sed -i '/^gamedll\t\t/a gamedll_linux\t"dlls/hl.so"' stargatetc/gameinfo.txt
```

(keep the stock `gamedll` metamod line; just add `gamedll_linux`). Deploy the built pair first: `cp hlsdk-portable/build-sgtc/dlls/hl.so stargatetc/dlls/hl.so` + `cl_dll/client.so` → `stargatetc/cl_dlls/client.so`.

## 4. Driving the mod

- **Console**: backtick toggles it; `type` only works while console is open. Each `type`+`enter` line echoes `>cmd` in the game log (`/tmp/xashrun/*.log`) — grep the log to prove a command was received.
- **Menus**: server pushes them via `ShowVGUIMenu`. Force one open: `vguimenuyoyo <id>` (10 briefing, 11 team/class, 12 weapon loadout, 60 pack select). Close: `hidevgui`.
- **Join (the non-obvious part)**: `jointeam N` alone does NOT spawn (and the port's client cmd table returns "Unknown command: jointeam" — server verb only). The real sequence is `classe <class> <team>` (e.g. `classe 1 1` = class 1, Torri) to set pending team+class fields → dead-tick `PlayerThink` consumes them → menu 60 (pack select) → Apply sends `gond4h9wp <28 slot values>` → respawn. `autopick`/`Auto Team` auto-assigns team but still needs a class to spawn — with no class it just joins and stays observer on BOTH builds.
- **All VGUI buttons are clickable** — see §5.

## 5. Input that actually works (verified 2026-10-15)

The earlier "VNC clicks don't reach VGUI buttons" claim was wrong — it was a coordinate bug. Verified on BOTH FreeVGUI (port) and wine-VGUI1 (orig):

- **Keys** (console toggle + typing): `~/.local/bin/vncdotool -s $S key '`'` / `type 'cmd'` / `key enter`. xdotool's `grave` does NOT toggle the console.
- **Mouse / VGUI ActionSignal clicks**: `xdotool` with a real-coordinate press/release:
  `DISPLAY=:78 xdotool mousemove X Y mousedown 1 sleep 0.6 mouseup 1`
  Confirmed firing on menu-10 Ok, menu-11 class cells, menu-60 pack cells + Apply (`gond4h9wp`), Auto Team.
- **Coordinates**: captures are 1024x768 but you view a 62% downscale — **real = scaled ÷ 0.62 (≈ ×1.613)**. Hit the element's true center; a few px off lands on the wrong cell (PACK rows are ~22px apart; menu-60 Apply's text center ≈ real y 668).
- Known-good points (real px): menu-10 Ok ≈ (461,706); menu-11 Auto Team ≈ (465,739); menu-60 Apply ≈ (330,668); menu-60 PACK cells ≈ (190,167+row*22).

## 6. Capture → compare workflow

1. Capture the reference frame on the orig (`capture`, then archive to `.rea/shot_orig_<surface>_vnc.png`).
2. Same display, same window size — kill orig, launch port, reproduce the same state via the same console/menu path, capture.
3. `convert a.png b.png +append cmp.png` for a side-by-side; view the PNG directly.
4. Verdicts recorded in `.rea/draw_audit.md` (gitignored working trail); promoted captures also under `.rea/`.

## 7. Gates (run from repo root, after any dlls/ or cl_dll/ change)

```bash
cmake --build hlsdk-portable/build-sgtc && cmake --build hlsdk-xash3d/build-sgtc
SGTC_TREE=hlsdk-portable python3 tests/test_exports.py    # 96 factories, 0 missing
SGTC_TREE=hlsdk-portable python3 tests/test_logic.py      # 52/52 same-behavior
SGTC_TREE=hlsdk-portable python3 tests/test_client_hud.py # errors=0
# same three with SGTC_TREE=hlsdk-xash3d
bash tests/playtest.sh                                    # OK: client smoke connected
```

Mirror rule: every `dlls/sgtc_*`/`cl_dll/sgtc_*` edit must be byte-identical across `hlsdk-portable/` and `hlsdk-xash3d/` (`diff -q` the touched files). Stock SDK files (player.cpp, client.cpp, vgui_*.cpp) legitimately differ between trees — don't "fix" those.

## 8. REA (reversing) rules

`.omp/rules/use-rea-tools-for-reversing.md`: use `mcp__rea_*` tools on `ref/` binaries — never `objdump`/`readelf`/`strings`/`nm` shell-outs on reference binaries. One Ghidra session at a time; import takes 60–120s and the first query often times out — retry. nm addresses are +0x10000 vs Ghidra on `ref/stc_i386.so`. Verify-then-fix: decompile the ref path BEFORE changing code; confirmed-faithful is a valid verdict.

## 9. Goal-loop / automation notes (how we run the long sessions)

- The work runs under omp goal mode (`check everything visually against the windows version…`): the loop continues across turns; completion requires direct current-state evidence for every deliverable, and unreachable-on-both-builds surfaces get documented rather than guessed.
- Long REA+fix slices go to `task` subagents (they have their own request budgets — the classe/PlayerThink port hit the 200-request cap and had to be resumed via `write agent://<id>` with a narrower scope). Keep agent slices disjoint (dlls vs cl_dll) or they collide.
- Status posts go to the ROW-50 automation webhook (`~/ops` pattern): milestones with summary/next/blockers + artifact links.
- All three repos push together: `hlsdk-portable` → origin master, `hlsdk-xash3d` → xash remote sgtc-port, root → origin main; release tag `sgtc-port-1.0` is moved, never re-versioned.
