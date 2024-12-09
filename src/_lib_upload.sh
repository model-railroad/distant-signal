#!/usr/bin/bash
set -e
D="/d /f /cygdrive/f"
C="code.py"
L="$1"

S=( $PWD/../setup/bundle/adafruit-circuitpython-bundle-*/lib/$L )
S="${S[0]}"

if [[ ! -d "$S" ]]; then
    # If it's not a directoy module, try a single file.
    S=( $PWD/../setup/bundle/adafruit-circuitpython-bundle-*/lib/${L}.mpy )
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

