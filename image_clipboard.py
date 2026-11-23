"""Publish PNG data to the desktop clipboard."""
import os
import shutil
import subprocess


def copy_png(data):
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        command = ["wl-copy", "--type", "image/png"]
    elif os.environ.get("DISPLAY") and shutil.which("xclip"):
        command = ["xclip", "-selection", "clipboard", "-t", "image/png", "-i"]
    else:
        raise RuntimeError("Install wl-clipboard for Wayland or xclip for X11.")
    subprocess.run(command, input=data, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=True, timeout=5)
