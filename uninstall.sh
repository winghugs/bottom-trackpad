#!/bin/bash
set -Ee

# root check
if [ $(id -u) -eq 0 ]
  then echo "Please do not run this script as root, try again without sudo."
  exit
fi

# don't continue if something fails
error_handler() {
    local exit_code="$?"
    echo ""
    echo "Script failed with exit code $exit_code."
    echo "Something went wrong. Check the output for errors."
}

trap error_handler ERR

echo "Uninstalling trackpad"

SCRIPT_DIR="$HOME/.local/share/badthortrackpad/"
SYSTEMD_CONFIG="$HOME/.config/systemd/user/"


# disable the service
systemctl --user stop auto-trackpad-thor.service || true
systemctl --user disable auto-trackpad-thor.service || true

# kill all the downloaded files
rm -rf "$SCRIPT_DIR"
rm -f "$SYSTEMD_CONFIG/auto-trackpad-thor.service"

# add and start service
systemctl --user daemon-reload

echo "Mission Complete! Please restart your Thor."

