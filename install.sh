#!/bin/sh
# install.sh -- build pi-desk (-O2) and install it for this user:
#   ~/.local/bin/pi-desk and a launcher entry in ~/.local/share/applications
set -e
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$here/build" "$HOME/.local/bin" "$HOME/.local/share/applications"
"$here/build.sh" "$here/app/pi/main.zeph" "$here/build/pi-desk" -O2
install -m 755 "$here/build/pi-desk" "$HOME/.local/bin/pi-desk"
cat > "$HOME/.local/share/applications/pi-desk.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=pi
GenericName=Coding agent
Comment=Desktop window for the pi coding agent
Exec=$HOME/.local/bin/pi-desk %f
Terminal=false
Categories=Development;
StartupWMClass=pi-desk
DESKTOP
echo "installed: $HOME/.local/bin/pi-desk"
