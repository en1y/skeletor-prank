# skeletor

A skeleton runs across the screen and the volume goes to max, then back to where it was. About once an hour. Harmless meme.

This project was made using AI.

## install

Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/en1y/skeletor-prank/main/install.sh | sh
```

Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/en1y/skeletor-prank/main/install.ps1 | iex
```

It asks how often to roll the dice and the chance of a strike on each roll, saves your answers on this computer, and starts at your next login. It needs Python 3, plus `mpv` on Linux for the see-through effect.

Run the same line again on a computer that already has it, and it offers to change the timings or erase it.

## how it works

`bad_to_the_bone.mp3` is the first 2 seconds of the clip (the riff). That audio is already inside `skeleton.mp4`.

The green in `skeleton.mp4` turns transparent as it plays, so the skeleton runs over your apps and clicks pass through to them. On Linux this needs `mpv`; any other player shows the green background. Windows needs nothing extra: a click-through window plays `skeleton.frames` and `skeleton.wav`, which `build_overlay.py` makes from the clip. A replacement clip needs the same green, or change `chromakey` in `skeletor.py`, then rerun `build_overlay.py`.

It installs into a dot-folder and one login entry, so it is not sitting on the desktop. Erase deletes that folder and that entry. Paths:

- linux: `~/.local/share/.skeletor` and `~/.config/autostart/skeletor.desktop`
- windows: `%LOCALAPPDATA%\.skeletor` and the Startup folder `skeletor.cmd`

From a checkout, `python3 install.py` opens a menu. Pick `1` to install, `2` to erase, or `3` to run it now.

## settings

Install asks for two numbers. Every so many seconds it rolls the dice, and the chance is the odds of a strike on that roll. Press Enter to keep the default.

| On average | Seconds between rolls | Chance |
|---|---|---|
| once an hour (default) | `60` | `1/60` |
| once every 10 minutes | `60` | `1/10` |
| once a day | `60` | `1/1440` |
| once an hour, rolling every second | `1` | `1/3600` |

These are averages, so two strikes can land close together. To change them, run the install line again and pick `1`, or edit `settings.json` in the install folder. The runner picks up the change after its next roll. Running `skeletor.py` from a checkout without `settings.json` uses the defaults at the top of the file.

## test

`python3 test_skeletor.py` checks the volume and dice logic without touching the real volume.

Plays it once, immediately:

```sh
python3 "$HOME/.local/share/.skeletor/install.py" run
```

```powershell
py "$env:LOCALAPPDATA\.skeletor\install.py" run
```

From a checkout, that is `python3 install.py run`.

## remove

This deletes the folder and the login entry, and stops the runner if it is going:

```sh
python3 "$HOME/.local/share/.skeletor/install.py" erase
```

```powershell
py "$env:LOCALAPPDATA\.skeletor\install.py" erase
```

Or by hand:

```sh
rm -rf "$HOME/.local/share/.skeletor"
rm -f "$HOME/.config/autostart/skeletor.desktop"
```

```powershell
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$env:LOCALAPPDATA\.skeletor"
Remove-Item -Force -ErrorAction SilentlyContinue "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\skeletor.cmd"
```
