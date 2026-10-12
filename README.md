# stargatetc-rea

StargateTC mod assets plus a Linux source port (`hlsdk-portable/`) rebuilt from
`ref/stc_i386.so` / `ref/sgtc2_dll/client.dll` with REA-assisted parity work.

## Build (Linux i386 game DLLs)

```bash
cmake -S hlsdk-portable -B hlsdk-portable/build-sgtc -DGAMEDIR=$PWD/stargatetc
make -C hlsdk-portable/build-sgtc -j$(nproc)
```

```bash
# mirror (hlsdk-xash3d): release for playtest, debug+SGTC_EXPORT_ALL_SYMBOLS for logic dlsym
cmake -S hlsdk-xash3d -B hlsdk-xash3d/build-sgtc -DGAMEDIR=$PWD/stargatetc -DCMAKE_BUILD_TYPE=Release
cmake --build hlsdk-xash3d/build-sgtc -- -j$(nproc)
cmake -S hlsdk-xash3d -B hlsdk-xash3d/build-dbg -DGAMEDIR=$PWD/stargatetc -DSGTC_EXPORT_ALL_SYMBOLS=ON -DCMAKE_BUILD_TYPE=Debug
cmake --build hlsdk-xash3d/build-dbg -- -j$(nproc)
```

## Verify exports + server logic

```bash
python3 tests/test_exports.py      # 96/96 SGTC factories, engine exports PASS
python3 tests/test_client_hud.py    # client_hud_spec errors=0 (vs ref client.dll)
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
