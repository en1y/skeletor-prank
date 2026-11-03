#!/usr/bin/env python3
"""Self-check. Fakes the audio tools, so it never touches the real volume:

    python3 test_skeletor.py
"""
import random
import shutil
import sys
import tempfile
import time

import skeletor


def fake_tool(tool, reads):
    """Only `tool` is installed. Commands in `reads` answer, the rest are recorded as writes."""
    writes = []
    shutil.which = lambda name: name if name == tool else None

    def sh(*cmd):
        for prefix, out in reads.items():
            if " ".join(cmd).startswith(prefix):
                return out
        writes.append(list(cmd))
        return ""

    skeletor.sh = sh
    return writes


def check_tool(tool, reads, up, back):
    writes = fake_tool(tool, reads)
    restore = skeletor.max_volume()
    assert writes == up, writes
    del writes[:]
    restore()
    assert writes == back, writes


s = "@DEFAULT_SINK@"
check_tool(
    "pactl",
    {
        "pactl get-sink-volume": "Volume: front-left: 26214 / 40% / -23.88 dB,   "
        "front-right: 19661 / 30% / -31.37 dB\n        balance -0.25\n",
        "pactl get-sink-mute": "Mute: yes\n",
    },
    [["pactl", "set-sink-mute", s, "0"], ["pactl", "set-sink-volume", s, "100%"]],
    [["pactl", "set-sink-volume", s, "26214", "19661"], ["pactl", "set-sink-mute", s, "yes"]],
)
s = "@DEFAULT_AUDIO_SINK@"
check_tool(
    "wpctl",
    {"wpctl get-volume": "Volume: 0.37 [MUTED]\n"},
    [["wpctl", "set-mute", s, "0"], ["wpctl", "set-volume", s, "1.0"]],
    [["wpctl", "set-volume", s, "0.37"], ["wpctl", "set-mute", s, "1"]],
)
check_tool(
    "amixer",
    {
        "amixer sget": "Simple mixer control 'Master',0\n  Limits: Playback 0 - 65536\n  Mono:\n"
        "  Front Left: Playback 32768 [50%] [off]\n  Front Right: Playback 32768 [50%] [off]\n"
    },
    [["amixer", "-q", "sset", "Master", "100%", "unmute"]],
    [["amixer", "-q", "sset", "Master", "50%", "off"]],
)

# Unreadable volume: nothing gets changed, so nothing is left stuck at max.
writes = fake_tool("pactl", {"pactl get-sink": ""})
skeletor.max_volume()()
assert writes == [], writes

# The volume goes back even when the player blows up.
restored = []


def boom():
    raise RuntimeError


skeletor.VIDEO = __file__
skeletor.max_volume = lambda: lambda: restored.append(True)
skeletor.play = boom
try:
    skeletor.jumpscare()
    raise AssertionError("play() should have raised")
except RuntimeError:
    pass
assert restored == [True]

# The loop rolls every CHECK_EVERY seconds and strikes only when the roll is under CHANCE.
strikes, slept = [], []
rolls = iter([0.9, 0.25, 0.1, 0.5])
skeletor.HERE = tempfile.mkdtemp()
skeletor.CHECK_EVERY, skeletor.CHANCE = 7, 0.25
skeletor.jumpscare = lambda: strikes.append(True)
time.sleep = slept.append
random.random = lambda: next(rolls)
sys.argv = ["skeletor.py"]
try:
    skeletor.main()
except StopIteration:
    pass
assert len(strikes) == 1, strikes
assert slept == [7] * 5, slept

print("ok")
