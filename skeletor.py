#!/usr/bin/env python3
"""skeletor — every so often the skeleton gets you: see-through clip + max volume.

Harmless meme. Runs a loop, rolls the dice every so often, strikes when it hits.
The volume goes back where it was after each strike.
Remove it with the script in the README, or: python3 install.py erase

    python3 skeletor.py           # loop forever, strike at random
    python3 skeletor.py --once    # strike right now
    python3 install.py run        # same, from the menu command
"""
import os
import re
import sys
import json
import time
import random
import shutil
import signal
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.join(HERE, "skeleton.mp4")

# Defaults, used unless install.py saved settings.json next to this file.
# Every CHECK_EVERY seconds it rolls the dice, and CHANCE is the odds of a strike.
CHECK_EVERY = 60   # seconds: 1 rolls every second, 60 every minute
CHANCE = 1 / 60    # 1/60 a minute averages one strike an hour


def load_settings():
    """(check_every, chance) from settings.json, or the defaults if it's missing or broken."""
    try:
        with open(os.path.join(HERE, "settings.json")) as f:
            saved = json.load(f)
        return float(saved["check_every"]), float(saved["chance"])
    except (OSError, ValueError, KeyError, TypeError):
        return CHECK_EVERY, CHANCE


def sh(*cmd):
    # LC_ALL=C because the output gets parsed and these tools translate it.
    env = {**os.environ, "LC_ALL": "C"}
    return subprocess.run(cmd, capture_output=True, text=True, check=False, env=env).stdout


def linux_volume():
    """(commands that max the volume, commands that put it back), or None if unreadable."""
    if shutil.which("pactl"):
        s = "@DEFAULT_SINK@"
        levels = re.findall(r"(\d+) /", sh("pactl", "get-sink-volume", s))  # raw, per channel
        mute = re.search(r"Mute: (yes|no)", sh("pactl", "get-sink-mute", s))
        if levels and mute:
            return (
                [["pactl", "set-sink-mute", s, "0"], ["pactl", "set-sink-volume", s, "100%"]],
                [["pactl", "set-sink-volume", s, *levels], ["pactl", "set-sink-mute", s, mute[1]]],
            )
    if shutil.which("wpctl"):
        s = "@DEFAULT_AUDIO_SINK@"
        m = re.search(r"Volume: ([\d.]+)( \[MUTED\])?", sh("wpctl", "get-volume", s))
        if m:
            return (
                [["wpctl", "set-mute", s, "0"], ["wpctl", "set-volume", s, "1.0"]],
                [["wpctl", "set-volume", s, m[1]], ["wpctl", "set-mute", s, "1" if m[2] else "0"]],
            )
    if shutil.which("amixer"):
        m = re.search(r"\[(\d+)%\].*\[(on|off)\]", sh("amixer", "sget", "Master"))
        if m:
            return (
                [["amixer", "-q", "sset", "Master", "100%", "unmute"]],
                [["amixer", "-q", "sset", "Master", m[1] + "%", m[2]]],
            )
    return None


def max_volume_windows():
    """max_volume for Windows, through raw COM so there's no pycaw dependency."""
    import ctypes
    import uuid
    from ctypes import c_char_p, c_float, c_int, c_void_p, pointer

    def call(obj, slot, *args):
        vtable = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *map(type, args))(vtable[slot])(obj, *args)

    guid = lambda s: c_char_p(uuid.UUID(s).bytes_le)
    ALL, NULL = c_int(23), c_void_p()
    enumerator, device, volume = c_void_p(), c_void_p(), c_void_p()
    ole32 = ctypes.oledll.ole32
    ole32.CoInitialize(None)
    ole32.CoCreateInstance(
        guid("BCDE0395-E52F-467C-8E3D-C4579291692E"), None, ALL,
        guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), pointer(enumerator),
    )
    call(enumerator, 4, c_int(0), c_int(1), pointer(device))  # GetDefaultAudioEndpoint(speakers, media)
    call(device, 3, guid("5CDF2C82-841E-4546-9722-0CF74078229A"), ALL, NULL, pointer(volume))  # Activate
    level, muted = c_float(), c_int()
    call(volume, 9, pointer(level))  # GetMasterVolumeLevelScalar
    call(volume, 15, pointer(muted))  # GetMute
    call(volume, 14, c_int(0), NULL)  # SetMute
    call(volume, 7, c_float(1.0), NULL)  # SetMasterVolumeLevelScalar

    def restore():
        try:
            call(volume, 7, level, NULL)
            call(volume, 14, muted, NULL)
        except OSError:
            pass  # device unplugged mid-strike

    return restore


def max_volume():
    """Turn the volume all the way up and return a function that puts it back."""
    # Can't read the level? Then it couldn't be put back, so it stays untouched.
    if sys.platform.startswith("win"):
        try:
            return max_volume_windows()
        except OSError:
            return lambda: None
    cmds = linux_volume()
    if not cmds:
        return lambda: None
    up, back = cmds
    for cmd in up:
        sh(*cmd)
    return lambda: [sh(*cmd) for cmd in back]


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
    # ponytail: can't tell when the OS player finishes, so hold the volume up a few seconds.
    time.sleep(5)


def jumpscare():
    if not os.path.exists(VIDEO):
        sys.exit("missing video: " + VIDEO)
    restore_volume = max_volume()
    try:
        play()
    finally:
        restore_volume()


def main():
    # So a kill mid-strike (erase, logout) still runs jumpscare's finally.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    if "--once" in sys.argv:
        jumpscare()
        return
    # ponytail: pid file so erase can stop this loop. no second copy, no watchdog.
    try:
        with open(os.path.join(HERE, "skeletor.pid"), "w") as f:
            f.write(str(os.getpid()))
    except OSError:
        pass
    check_every, chance = load_settings()
    while True:
        time.sleep(check_every)
        if random.random() < chance:
            jumpscare()


if __name__ == "__main__":
    main()
