#!/usr/bin/bash
set -e
D="/d /f /cygdrive/f"
C="code.py"

for d in $D; do
    if [[ -f "$d/$C" ]]; then
        echo "OK: Using $d/$C"
        cp -v "$C" "$d/$C"
        exit 0
    fi
done

echo "FAILED: $C not found in $D"

