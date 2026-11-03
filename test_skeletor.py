#!/usr/bin/env python3
"""Self-check. Fakes the audio tools, so it never touches the real volume:

    python3 test_skeletor.py
"""
import builtins
import contextlib
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

import install
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

# settings.json from the installer beats the defaults, and a broken one falls back to them.
settings = os.path.join(skeletor.HERE, "settings.json")
with open(settings, "w") as f:
    json.dump({"check_every": 3, "chance": 0.75}, f)
del strikes[:], slept[:]
rolls = iter([0.9, 0.5])
try:
    skeletor.main()
except StopIteration:
    pass
assert len(strikes) == 1, strikes
assert slept == [3] * 3, slept
with open(settings, "w") as f:
    f.write("not json")
assert skeletor.load_settings(skeletor.HERE) == (7, 0.25)
with open(settings, "w") as f:
    json.dump({"check_every": 0, "chance": 0.5}, f)
assert skeletor.load_settings(skeletor.HERE) == (7, 0.25)


# New timings reach a runner that's already going, after its next roll.
def sleep_then_edit(seconds):
    slept.append(seconds)
    with open(settings, "w") as f:
        json.dump({"check_every": 9, "chance": 0.75}, f)


with open(settings, "w") as f:
    json.dump({"check_every": 3, "chance": 0.75}, f)
del slept[:]
rolls = iter([0.9])
time.sleep = sleep_then_edit
try:
    skeletor.main()
except StopIteration:
    pass
assert slept == [3, 9], slept


# The installer keeps asking until an answer fits. Enter or no terminal takes the default.
def typing(*typed):
    pending = iter(typed)
    prompts = []

    def fake_input(prompt):
        prompts.append(prompt)
        for answer in pending:
            return answer
        raise EOFError

    builtins.input = fake_input
    return prompts


def answers(*typed):
    typing(*typed)
    with contextlib.redirect_stdout(io.StringIO()):
        return install.ask("q", "1/60", lambda v: 0 <= v <= 1, "rule")


assert answers("abc", "1/0", "2", "-1", "1/4") == 0.25
assert answers("0.5") == 0.5
assert answers("") == 1 / 60
assert answers() == 1 / 60

# Already installed: it offers new timings or erase, and anything else changes nothing.
home = tempfile.mkdtemp(prefix="Ivančić Жанна 日本語 ")
folder = os.path.join(home, "skeletor")
link = os.path.join(home, "autostart", "skeletor.desktop")
install.dest = lambda: folder
install.autostart = lambda: link


def run_install(*typed):
    prompts = typing(*typed)
    with contextlib.redirect_stdout(io.StringIO()):
        install.install()
    return prompts


assert len(run_install("20", "1/2")) == 2
assert skeletor.load_settings(folder) == (20, 0.5)
for typed in ([""], ["3"], ["nonsense"], []):
    assert len(run_install(*typed)) == 1, typed
    assert skeletor.load_settings(folder) == (20, 0.5), typed
    assert os.path.exists(link), typed
prompts = run_install("1", "", "1/4")
assert "[20]" in prompts[1] and "[1/2]" in prompts[2], prompts
assert skeletor.load_settings(folder) == (20, 0.25)
run_install("2")
assert not os.path.exists(folder) and not os.path.exists(link)

# Half an install isn't installed: a normal install puts the missing part back.
run_install("20", "1/2")
os.remove(link)
assert len(run_install()) == 2
assert os.path.exists(link)

# Any character in a path installs fine, even where the default encoding can't write it.
real_open = builtins.open


def code_page_open(file, mode="r", buffering=-1, encoding=None, **kw):
    return real_open(file, mode, buffering, encoding or (None if "b" in mode else "ascii"), **kw)


builtins.open = code_page_open
run_install("2")
run_install("20", "1/2")
builtins.open = real_open
with open(link, encoding="utf-8") as f:
    assert folder in f.read()
with open(os.path.join(folder, "REMOVE.txt"), encoding="utf-8") as f:
    assert link in f.read()

# Login entries keep every path intact, on both systems.
real_platform = sys.platform
sys.platform = "win32"
assert install.login_entry("C:\\Ivančić\\pythonw.exe", "C:\\100%\\Жанна\\skeletor.py") == (
    '@echo off\nchcp 65001 >nul\nstart "" "C:\\Ivančić\\pythonw.exe" "C:\\100%%\\Жанна\\skeletor.py"\n'
)
# Inside the profile, the entry stays plain ASCII so no code page can garble it.
os.environ["LOCALAPPDATA"] = "C:\\Users\\Ivančić\\AppData\\Local"
entry = install.login_entry(
    "C:\\Users\\Ivančić\\AppData\\Local\\Programs\\Python\\pythonw.exe",
    "C:\\USERS\\IVANČIĆ\\AppData\\Local\\.skeletor\\skeletor.py",
)
assert entry.isascii() and '"%LOCALAPPDATA%\\.skeletor\\skeletor.py"' in entry, entry
os.environ["LOCALAPPDATA"] = "C:\\Users\\Ivan"
assert "%LOCALAPPDATA%" not in install.batch_path("C:\\Users\\Ivančić\\x"), "only whole folder names match"
del os.environ["LOCALAPPDATA"]
sys.platform = "linux"
entry = install.login_entry("/usr/bin/python3", '/home/Жанна/a "b" $c 100%/skeletor.py')
assert 'Exec="/usr/bin/python3" "/home/Жанна/a \\\\"b\\\\" \\\\$c 100%%/skeletor.py"\n' in entry
sys.platform = real_platform

# Printing those paths to a pipe doesn't crash either. All the install paths point at a temp folder.
piped = tempfile.mkdtemp(prefix="Ivančić Жанна 日本語 ")
env = dict(os.environ, HOME=piped, USERPROFILE=piped, LOCALAPPDATA=piped, APPDATA=piped, PYTHONIOENCODING="ascii")
result = subprocess.run([sys.executable, "-B", install.__file__, "erase"], env=env, capture_output=True)
assert result.returncode == 0 and "Ivančić Жанна 日本語".encode() in result.stdout, result

# The Windows frames fit the screen area and are premultiplied, or they'd show bright edges.
head, data = skeletor.load_frames()
box_w, box_h = head["box"]
spots = [s for s in head["frames"] if s]
assert spots and len(data) == len(spots) * box_w * box_h * 4
assert all(0 <= x <= head["width"] - box_w and 0 <= y <= head["height"] - box_h for x, y, _ in spots)
assert [i for _, _, i in spots] == list(range(len(spots)))
assert all(max(data[p:p + 3]) <= data[p + 3] for p in range(0, len(data), 4 * 997))
assert any(data[3::4]) and data.count(0) > len(data) // 2

print("ok")
