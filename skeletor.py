#!/usr/bin/env python3
"""skeletor — every so often the skeleton gets you: see-through clip + max volume.

Harmless meme. Runs a loop, sleeps a random while, then strikes.
Remove it with the script in the README, or: python3 install.py erase

    python3 skeletor.py           # loop forever, strike at random
    python3 skeletor.py --once    # strike right now
    python3 install.py run        # same, from the menu command
"""
import os
import sys
import time
import random
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.join(HERE, "skeleton.mp4")

MIN_WAIT = 20 * 60   # seconds between strikes (random in this range)
MAX_WAIT = 90 * 60


def max_volume():
    if sys.platform.startswith("win"):
        import ctypes
        # ponytail: tap the volume-up media key 50x — pure ctypes, no deps.
        # ceiling: won't unmute a muted system; swap in nircmd if that matters.
        VK_VOLUME_UP, KEYUP = 0xAF, 0x0002
        for _ in range(50):
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_VOLUME_UP, 0, KEYUP, 0)
    else:
        for cmd in (
            ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "0"],
            ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "100%"],
            ["amixer", "-q", "sset", "Master", "100%", "unmute"],
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "1.0"],
        ):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, check=False)


def play():
    # ponytail: mpv keys out the clip's green live, so the video stays a plain mp4.
    # crop trims the black lines on the clip's edges, despill removes the green fringe.
    # knob: chromakey similarity:blend. raise if green shows, lower if bones vanish.
    # ceiling: only mpv does this, the players below show the green background.
    # no key bindings: a stray space would pause it, leaving an invisible fullscreen window.
    overlay = [
        "mpv", "--fs", "--really-quiet", "--no-config", "--no-osc",
        "--no-input-default-bindings", "--input-cursor-passthrough=yes",
        "--background=none", "--border-background=none",
        "--vf=lavfi=[crop=iw-16:ih-16:8:8,format=rgba,chromakey=0x00D506:0.2:0.05,despill=type=green]",
        VIDEO,
    ]
    if sys.platform.startswith("win"):
        overlay.insert(1, "--d3d11-flip=no")  # mpv needs this for transparency on d3d11
    # First player that's actually installed wins; each goes fullscreen + exits.
    for p in (
        overlay,
        ["ffplay", "-fs", "-autoexit", "-loglevel", "quiet", VIDEO],
        ["vlc", "--fullscreen", "--play-and-exit", "--no-video-title-show", VIDEO],
    ):
        if shutil.which(p[0]):
            subprocess.run(p, check=False)
            return
    # ponytail: no real player found → hand it to the OS default (not fullscreen).
    if sys.platform.startswith("win"):
        os.startfile(VIDEO)  # type: ignore[attr-defined]
    elif shutil.which("xdg-open"):
        subprocess.run(["xdg-open", VIDEO], check=False)


def jumpscare():
    if not os.path.exists(VIDEO):
        sys.exit("missing video: " + VIDEO)
    max_volume()
    play()


def main():
    if "--once" in sys.argv:
        jumpscare()
        return
    # ponytail: pid file so erase can stop this loop. no second copy, no watchdog.
    try:
        with open(os.path.join(HERE, "skeletor.pid"), "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    while True:
        time.sleep(random.randint(MIN_WAIT, MAX_WAIT))
        jumpscare()


if __name__ == "__main__":
    main()
