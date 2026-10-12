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

echo "This line will never be reached because of set -e"

echo "**** WARNING ****"
echo "This script enables and adds a python script that allows use of bottom screen as a trackpad."
echo "Do not install this on any device other than the AYN Thor."
read -n 1 -s -r -p "Press any key to continue, or CTRL+C to quit"
echo

CURRENT_DIR="$(pwd)"
SCRIPT_DIR="$HOME/.local/share/badthortrackpad/"
SYSTEMD_CONFIG="$HOME/.config/systemd/user/"

# setup folders
mkdir -p "$SCRIPT_DIR"
mkdir -p "$SYSTEMD_CONFIG"

# put the files where they need to be
cd "$SCRIPT_DIR"
curl https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/trackpad.py > trackpad.py
chmod +x trackpad.py
curl "https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/start.sh" > "start.sh"
curl "https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/stop.sh" > "stop.sh"
cd "$SYSTEMD_CONFIG"
curl https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/auto-trackpad-thor.service > auto-trackpad-thor.service
cd "$CURRENT_DIR"

# add and start service
systemctl --user daemon-reload
systemctl --user enable --now auto-trackpad-thor.service
