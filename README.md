# bottom-trackpad

## what this does
Adds a service to start a lil trackpad on your bottom screen when you boot your thor. This trackpad is invisible and just turns your bottom screen into a normal trackpad.

To turn off the trackpad (and back on) you should add two non-steam games. I'm sorry.

Off:
```
Name: Turn Off Trackpad
Executable: "/usr/bin/systemctl"
Starting Dir: /usr/bin
Launch Arguments: "%command% --user stop auto-trackpad-thor.service"
```

On:
```
Name: Turn On Trackpad
Executable: "/usr/bin/systemctl"
Starting Dir: /usr/bin
Launch Arguments: "%command% --user start auto-trackpad-thor.service"
```

## this thing is pretty bad and i hope other people make better things than this in the future

## Install
Copy and paste this into your terminal:
``` sh -c "$(curl -fsSL https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/setup.sh)"```

## Uninstall
Copy and paste this into your terminal:
``` sh -c "$(curl -fsSL https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/uninstall.sh)"```
