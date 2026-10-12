# stargatetc-rea

StargateTC mod assets plus a Linux source port (`hlsdk-portable/`) rebuilt from
`ref/stc_i386.so` / `ref/sgtc2_dll/client.dll` with REA-assisted parity work.

## Build (Linux i386 game DLLs)

```bash
cmake -S hlsdk-portable -B hlsdk-portable/build-sgtc -DGAMEDIR=$PWD/stargatetc
make -C hlsdk-portable/build-sgtc -j$(nproc)
```

## Verify exports + server logic

```bash
python3 tests/test_exports.py      # 96/96 SGTC factories, engine exports PASS
python3 tests/test_logic.py        # 52/52 behavioral matrix vs ref stc_i386.so
./tests/playtest.sh                # deploy hl.so + client.so; Xash smoke (needs 32-bit FWGS + XASH3D_BASEDIR)

# same gate chain against the hlsdk-xash3d mirror (build build-sgtc + build-dbg there first):
SGTC_TREE=hlsdk-xash3d python3 tests/test_exports.py
SGTC_TREE=hlsdk-xash3d python3 tests/test_client_hud.py
SGTC_TREE=hlsdk-xash3d python3 tests/test_logic.py
SGTC_TREE=hlsdk-xash3d ./tests/playtest.sh
```

Upstream mod pack: https://github.com/jr551/stargatetc-portable/archive/refs/heads/main.zip
Source port repo: https://github.com/jr551/sgtc1-hlsdk-portable
