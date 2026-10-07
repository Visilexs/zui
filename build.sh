#!/bin/sh
# build.sh <entry.zeph> <output> [-O2] -- compile a zui program (pure Zephyr;
# SDL3, FreeType and fontconfig are loaded at run time through extern fn).
set -e
here="$(cd "$(dirname "$0")" && pwd)"
zc="${ZC:-$here/../zephyr/zc}"
"$zc" --version | grep -q linux-extern || { echo "needs a zc with linux-extern (Zephyr dynamic linking)" >&2; exit 1; }
"$zc" ${3:-} --linux --rt "$1" "$2"
chmod +x "$2"
