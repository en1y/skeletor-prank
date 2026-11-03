#!/usr/bin/env python3
"""Rebuild skeleton.frames and skeleton.wav from skeleton.mp4. Needs ffmpeg.

Windows plays these instead of the mp4, because Python alone can't decode video
and its sound module only plays wav. Rerun after changing the clip or KEY.
"""
import json
import subprocess
import wave
import zlib

from skeletor import FRAMES, KEY, VIDEO, WAV

WIDTH, HEIGHT = 1264, 704  # skeleton.mp4 after KEY's crop
FPS = 30

raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", VIDEO, "-vf", KEY, "-f", "rawvideo", "-pix_fmt", "bgra", "-"],
    capture_output=True, check=True,
).stdout
frame_size = WIDTH * HEIGHT * 4
assert len(raw) % frame_size == 0, "frame size is off: update WIDTH and HEIGHT"
frames = [raw[i:i + frame_size] for i in range(0, len(raw), frame_size)]


def bounds(frame):
    """(left, top, right, bottom) of the visible pixels, or None for an empty frame."""
    alpha = frame[3::4]
    rows = [y for y in range(HEIGHT) if any(alpha[y * WIDTH:(y + 1) * WIDTH])]
    if not rows:
        return None
    top, bottom = rows[0], rows[-1] + 1
    cols = [x for x in range(WIDTH) if any(alpha[top * WIDTH + x:bottom * WIDTH:WIDTH])]
    return cols[0], top, cols[-1] + 1, bottom


# Every frame shares one box size, so the player can reuse a single bitmap.
found = [bounds(f) for f in frames]
box_w = max(b[2] - b[0] for b in found if b)
box_h = max(b[3] - b[1] for b in found if b)

spots, blocks = [], bytearray()
for frame, b in zip(frames, found):
    if not b:
        spots.append(None)
        continue
    x, y = min(b[0], WIDTH - box_w), min(b[1], HEIGHT - box_h)
    spots.append([x, y, len(blocks) // (box_w * box_h * 4)])
    for row in range(y, y + box_h):
        line = frame[(row * WIDTH + x) * 4:(row * WIDTH + x + box_w) * 4]
        for p in range(0, len(line), 4):
            a = line[p + 3]
            blocks += bytes((line[p] * a // 255, line[p + 1] * a // 255, line[p + 2] * a // 255, a))

subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", VIDEO, "-vn", "-c:a", "pcm_s16le", WAV], check=True)
with wave.open(WAV) as w:
    seconds = w.getnframes() / w.getframerate()

head = {"width": WIDTH, "height": HEIGHT, "fps": FPS, "seconds": seconds, "box": [box_w, box_h], "frames": spots}
with open(FRAMES, "wb") as f:
    f.write(json.dumps(head).encode() + b"\n" + zlib.compress(bytes(blocks), 9))
print("box %dx%d, %d frames shown, %.2f seconds" % (box_w, box_h, sum(1 for s in spots if s), seconds))
