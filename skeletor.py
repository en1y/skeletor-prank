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
import traceback
import zlib
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.join(HERE, "skeleton.mp4")
# Windows only, both made from the clip by build_overlay.py.
FRAMES = os.path.join(HERE, "skeleton.frames")
WAV = os.path.join(HERE, "skeleton.wav")

# Turns the clip's green transparent. crop trims the black lines on its edges, despill
# removes the green fringe. knob: chromakey similarity:blend. raise if green shows, lower
# if bones vanish, then rerun build_overlay.py.
KEY = "crop=iw-16:ih-16:8:8,format=rgba,chromakey=0x00D506:0.2:0.05,despill=type=green"

# Defaults, used unless install.py saved settings.json next to this file.
# Every CHECK_EVERY seconds it rolls the dice, and CHANCE is the odds of a strike.
CHECK_EVERY = 60   # seconds: 1 rolls every second, 60 every minute
CHANCE = 1 / 60    # 1/60 a minute averages one strike an hour


def load_settings(folder):
    """(check_every, chance) from folder's settings.json, or the defaults if missing or broken."""
    try:
        with open(os.path.join(folder, "settings.json")) as f:
            saved = json.load(f)
        every, chance = float(saved["check_every"]), float(saved["chance"])
    except (OSError, ValueError, KeyError, TypeError):
        return CHECK_EVERY, CHANCE
    if 1 <= every <= 86400 and 0 <= chance <= 1:
        return every, chance
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


def load_frames():
    """(header, frames), where frames holds box-sized blocks of premultiplied BGRA."""
    with open(FRAMES, "rb") as f:
        head = json.loads(f.readline())
        return head, zlib.decompress(f.read())


def play_windows_overlay():
    """Run the clip over the desktop in a click-through window. Standard library only."""
    # ponytail: primary monitor only. a fullscreen-exclusive game can still cover it.
    import ctypes
    import struct
    import winsound
    from ctypes import byref, c_int, c_uint32, c_void_p, wintypes as w

    head, data = load_frames()
    box_w, box_h = head["box"]
    block = box_w * box_h * 4

    def api(dll, name, args, ret=w.BOOL):
        # Handles are pointer-sized, so ctypes' default of int would cut them off.
        fn = getattr(dll, name)
        fn.argtypes, fn.restype = args, ret
        return fn

    user32, gdi32 = ctypes.WinDLL("user32"), ctypes.WinDLL("gdi32")
    msimg32 = ctypes.WinDLL("msimg32")
    create_window = api(
        user32, "CreateWindowExW",
        [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, c_int, c_int, c_int, c_int,
         w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID],
        w.HWND,
    )
    destroy_window = api(user32, "DestroyWindow", [w.HWND])
    show_window = api(user32, "ShowWindow", [w.HWND, c_int])
    get_dc = api(user32, "GetDC", [w.HWND], w.HDC)
    release_dc = api(user32, "ReleaseDC", [w.HWND, w.HDC], c_int)
    update_layered = api(
        user32, "UpdateLayeredWindow",
        [w.HWND, w.HDC, ctypes.POINTER(w.POINT), ctypes.POINTER(w.SIZE), w.HDC,
         ctypes.POINTER(w.POINT), w.DWORD, ctypes.POINTER(c_uint32), w.DWORD],
    )
    peek_message = api(user32, "PeekMessageW", [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT])
    dispatch_message = api(user32, "DispatchMessageW", [ctypes.POINTER(w.MSG)], c_void_p)
    screen_size = api(user32, "GetSystemMetrics", [c_int], c_int)
    create_dc = api(gdi32, "CreateCompatibleDC", [w.HDC], w.HDC)
    delete_dc = api(gdi32, "DeleteDC", [w.HDC])
    create_dib = api(
        gdi32, "CreateDIBSection",
        [w.HDC, ctypes.c_char_p, w.UINT, ctypes.POINTER(c_void_p), w.HANDLE, w.DWORD],
        w.HBITMAP,
    )
    select_object = api(gdi32, "SelectObject", [w.HDC, w.HGDIOBJ], w.HGDIOBJ)
    delete_object = api(gdi32, "DeleteObject", [w.HGDIOBJ])
    stretch_mode = api(gdi32, "SetStretchBltMode", [w.HDC, c_int], c_int)
    flush = api(gdi32, "GdiFlush", [])
    alpha_blend = api(
        msimg32, "AlphaBlend",
        [w.HDC, c_int, c_int, c_int, c_int, w.HDC, c_int, c_int, c_int, c_int, c_uint32],
    )

    def bitmap(dc, width, height):
        # Negative height: rows run top to bottom, the same order as the frames.
        info = struct.pack("<IiiHHIIiiII", 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = c_void_p()
        handle = create_dib(dc, info, 0, byref(bits), None, 0)
        if not handle:
            raise OSError("CreateDIBSection failed")
        select_object(dc, handle)
        return handle, bits

    user32.SetProcessDPIAware()
    screen_w, screen_h = screen_size(0), screen_size(1)
    scale = min(screen_w / head["width"], screen_h / head["height"])
    left = (screen_w - head["width"] * scale) / 2
    top = (screen_h - head["height"] * scale) / 2
    out_w, out_h = round(box_w * scale), round(box_h * scale)
    OPAQUE_BLEND = 0x01FF0000  # BLENDFUNCTION: source over, per-pixel alpha
    LAYERED, CLICK_THROUGH, TOPMOST, NO_TASKBAR, NO_FOCUS = 0x80000, 0x20, 0x8, 0x80, 0x8000000
    POPUP, HIDE, SHOW_NO_FOCUS, HALFTONE, ULW_ALPHA = 0x80000000, 0, 4, 4, 2

    window = create_window(
        LAYERED | CLICK_THROUGH | TOPMOST | NO_TASKBAR | NO_FOCUS, "Static", None, POPUP,
        0, 0, out_w, out_h, None, None, None, None,
    )
    if not window:
        raise OSError("CreateWindowExW failed")
    screen = get_dc(None)
    src_dc, out_dc = create_dc(screen), create_dc(screen)
    src, out = None, None
    try:
        src, src_bits = bitmap(src_dc, box_w, box_h)
        out, out_bits = bitmap(out_dc, out_w, out_h)
        stretch_mode(out_dc, HALFTONE)
        try:
            winsound.PlaySound(WAV, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except RuntimeError:
            pass  # no sound device: still show it
        message, shown, start = w.MSG(), -1, time.time()
        while time.time() - start < head["seconds"]:
            while peek_message(byref(message), None, 0, 0, 1):
                dispatch_message(byref(message))
            now = int((time.time() - start) * head["fps"])
            if now == shown or now >= len(head["frames"]):
                time.sleep(0.002)
                continue
            shown = now
            spot = head["frames"][now]
            if spot is None:
                show_window(window, HIDE)
                continue
            x, y, i = spot
            ctypes.memmove(src_bits, data[i * block:(i + 1) * block], block)
            ctypes.memset(out_bits, 0, out_w * out_h * 4)
            alpha_blend(out_dc, 0, 0, out_w, out_h, src_dc, 0, 0, box_w, box_h, OPAQUE_BLEND)
            flush()
            ok = update_layered(
                window, screen, byref(w.POINT(round(left + x * scale), round(top + y * scale))),
                byref(w.SIZE(out_w, out_h)), out_dc, byref(w.POINT(0, 0)), 0,
                byref(c_uint32(OPAQUE_BLEND)), ULW_ALPHA,
            )
            if not ok:
                raise OSError("UpdateLayeredWindow failed")
            show_window(window, SHOW_NO_FOCUS)
    finally:
        destroy_window(window)
        delete_dc(src_dc)
        delete_dc(out_dc)
        for handle in (src, out):
            if handle:
                delete_object(handle)
        release_dc(None, screen)


def play():
    if sys.platform.startswith("win"):
        try:
            play_windows_overlay()
            return
        except Exception:
            # A broken overlay mustn't stop the runner: the players below still show the clip.
            traceback.print_exc()
    # ponytail: mpv keys out the clip's green live, so the video stays a plain mp4.
    # ceiling: only mpv does this, the players below show the green background.
    # no key bindings: a stray space would pause it, leaving an invisible fullscreen window.
    overlay = [
        "mpv", "--fs", "--really-quiet", "--no-config", "--no-osc",
        "--no-input-default-bindings", "--input-cursor-passthrough=yes",
        "--background=none", "--border-background=none",
        "--vf=lavfi=[%s]" % KEY, VIDEO,
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
    while True:
        # Read every time, so new timings apply without a restart.
        check_every, chance = load_settings(HERE)
        time.sleep(check_every)
        if random.random() < chance:
            jumpscare()


if __name__ == "__main__":
    main()
