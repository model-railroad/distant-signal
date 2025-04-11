#!/usr/bin/bash
set -e
D="/d /f /cygdrive/f"
C="code.py"
E="script_parser.py script_loader.py default_script.json"

for d in $D; do
    if [[ -f "$d/$C" ]]; then
        echo "OK: Using $d/$C"
        for e in $E; do
            cp -v "$e" "$d/$e"
        done
        cp -v "$C" "$d/$C"
        exit 0
    fi
done

echo "FAILED: $C not found in $D"

