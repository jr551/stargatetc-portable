#!/bin/bash
cd /home/john/stargatetc-rea
exec env DISPLAY=:78 XASH3D_BASEDIR=/home/john/stargatetc-rea XASH3D_GAME=stargatetc \
LD_LIBRARY_PATH=/home/john/stargatetc-rea/hlsdk-portable/build-sgtc/freevgui:/tmp/xash3d-fwgs/build/engine:/tmp/xash3d-fwgs/build/filesystem:/tmp/xash3d-fwgs/build/ref/gl:/tmp/xash3d-fwgs/build/game_launch \
/tmp/xash3d-fwgs/build/game_launch/xash3d -dev 2 -ref gl -game stargatetc -dll dlls/hl.so -window -width 1024 -height 768 +sv_lan 1 +map ctp_amon +maxplayers 8 +name pwpn > /tmp/xashrun/pwpn.log 2>&1
