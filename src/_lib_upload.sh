#!/usr/bin/bash
D="/d /f /cygdrive/f"
C="code.py"
L="$1"

if [[ ! -f "$C" ]]; then
    echo "FAILED: Please run this from the src directory."
    exit 1
fi

S="../lib/$L"
if [[ ! -d "$S" ]]; then
    S="../lib/${L}.mpy"
fi

if [[ ! -e "$S" ]]; then
    LD=$( ls -d \
        $PWD/../setup/bundle/adafruit-circuitpython-bundle-*/lib \
        $PWD/../../../*/*/*/setup/bundle/adafruit-circuitpython-bundle-*/lib \
        2>/dev/null
    )
    LD="${LD[0]}"

    S=( "$LD/$L" )
    S="${S[0]}"

    if [[ ! -d "$S" ]]; then
        # If it's not a directoy module, try a single file.
        S=( "$LD/${L}.mpy" )
        S="${S[0]}"
    fi
fi

if [[ ! -e "$S" ]]; then
    echo "FAILED: Cannot find library '$L' in $S"
    exit 1
fi

set -e

for d in $D; do
    if [[ -f "$d/$C" && -d "$d/lib" ]]; then
        echo "OK: Using $d/lib"
        cp -rv "$S" "$d/lib/"
        exit 0
    fi
done

echo "FAILED: $C and /lib not found in $D"

