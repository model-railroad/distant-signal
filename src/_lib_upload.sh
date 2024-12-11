#!/usr/bin/bash
D="/d /f /cygdrive/f"
C="code.py"
L="$1"

LD=$( ls -d \
     $PWD/../setup/bundle/adafruit-circuitpython-bundle-*/lib \
     $PWD/../../../*/*/*/setup/bundle/adafruit-circuitpython-bundle-*/lib \
     2>/dev/null
  )
LD="${LD[0]}"

set -e

S=( "$LD/$L" )
S="${S[0]}"

if [[ ! -d "$S" ]]; then
    # If it's not a directoy module, try a single file.
    S=( "$LD/${L}.mpy" )
    S="${S[0]}"
fi

if [[ ! -e "$S" ]]; then
    echo "FAILED: Cannot find library '$L' in $S"
    exit 1
fi

for d in $D; do
    if [[ -f "$d/$C" && -d "$d/lib" ]]; then
        echo "OK: Using $d/lib"
        cp -rv "$S" "$d/lib/"
        exit 0
    fi
done

echo "FAILED: $C and /lib not found in $D"

