#!/bin/bash
cd /home/john/src/StargateTC/project/stargatetc-portable-main
exec env DISPLAY=:78 LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe \
WINEPREFIX=/tmp/xashrun/prefix WINEDEBUG=-all \
wine xash3d.exe -game stargatetc -dev 2 -log -ref gl +sv_lan 1 +map ctp_amon +maxplayers 8 +name origwpn >> /tmp/xashrun/origwpn.log 2>&1
