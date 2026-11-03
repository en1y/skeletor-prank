#!/bin/sh
# curl -fsSL https://raw.githubusercontent.com/en1y/skeletor-prank/main/install.sh | sh
set -eu

RAW="${RAW:-https://raw.githubusercontent.com/en1y/skeletor-prank/main}"

# In a function so a cut-off download can't run half of this.
main() {
    if ! command -v python3 >/dev/null 2>&1; then
        echo "python3 is not installed" >&2
        exit 1
    fi
    d=$(mktemp -d)
    trap 'rm -rf "$d"' EXIT
    for f in install.py skeletor.py skeleton.mp4; do
        curl -fsSL "$RAW/$f" -o "$d/$f"
    done
    # stdin is this script when piped, so the questions have to read the terminal.
    if (: </dev/tty) 2>/dev/null; then
        python3 "$d/install.py" install </dev/tty
    else
        python3 "$d/install.py" install </dev/null
    fi
}

main
