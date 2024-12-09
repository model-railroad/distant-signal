#!/usr/bin/bash
set -e
set -x
N=adafruit-circuitpython-bundle-9.x-mpy-20241128.zip
if [[ ! -f "$N" ]]; then
    wget https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/download/20241128/$N
fi
if [[ ! -d bundle ]]; then
    mkdir bundle
    pushd bundle
    unzip ../$N
fi
