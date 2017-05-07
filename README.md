# i3blocks-networking-blocklet
i3blocks networking blocklet that scans for active interfaces in the system and displays them.

It scans for both logical and physical interfaces and prints them out in a pango
format (`markup=pango` needs to be set in i3blocks config

# Requirements
Python 3 and fontawesome

# Instalation
Download the `networking.py` file and add
```
[networking]
command=path/to/networking.py [--hide-totals] [--hide-physical] [--hide-logical]
interval=5
markup=pango
```
into `i3blocks.conf`.

For more information run `networking.py -h`.

