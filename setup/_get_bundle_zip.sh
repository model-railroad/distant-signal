#!/usr/bin/bash
set -e
set -x
D=20250319
N=adafruit-circuitpython-bundle-9.x-mpy-$D.zip
if [[ ! -f "$N" ]]; then
    wget https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/download/$D/$N
fi
if [[ ! -d bundle ]]; then
    mkdir bundle
    pushd bundle
    unzip ../$N
fi
