# bottom-trackpad

## what this does
Adds a service to start a lil trackpad on your bottom screen when you boot your thor. This trackpad is invisible and just turns your bottom screen into a normal trackpad.

To turn off the trackpad (and back on) you should add two non-steam games. I'm sorry.

Off:
```
Name: Turn Off Trackpad
Executable: "/bin/bash /var/home/armada/.local/badthortrackpad/stop.sh"
Starting Dir: /var/home/armada/.local/badthortrackpad/
Launch Arguments: 
```

On:
```
Name: Turn On Trackpad
Executable: "/bin/bash /var/home/armada/.local/badthortrackpad/start.sh"
Starting Dir: /var/home/armada/.local/badthortrackpad/
Launch Arguments: 
```

## this thing is pretty bad and i hope other people make better things than this in the future

## Install
Copy and paste this into your terminal:
``` sh -c "$(curl -fsSL https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/setup.sh)"```

## Uninstall
Copy and paste this into your terminal:
``` sh -c "$(curl -fsSL https://raw.githubusercontent.com/winghugs/bottom-trackpad/refs/heads/main/uninstall.sh)"```
