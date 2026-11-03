# skeletor

A skeleton runs across the screen and the volume goes to max, then back to where it was. About once an hour. Harmless meme.

This project was made using AI.

`bad_to_the_bone.mp3` is the first 2 seconds of the clip (the riff). That audio is already inside `skeleton.mp4`.

The green in `skeleton.mp4` turns transparent as it plays, so the skeleton runs over your apps and clicks pass through to them. This needs `mpv`; any other player shows the green background. A replacement clip needs the same green, or change `chromakey` in `skeletor.py`.

It installs into a dot-folder and one login entry, so it is not sitting on the desktop. Erase deletes that folder and that entry. Paths:

- linux: `~/.local/share/.skeletor` and `~/.config/autostart/skeletor.desktop`
- windows: `%LOCALAPPDATA%\.skeletor` and the Startup folder `skeletor.cmd`

From a checkout, `python3 install.py` opens the same menu. Pick `1` to install, `2` to erase, or `3` to run it now.

## settings

Install asks for two numbers. Every so many seconds it rolls the dice, and the chance is the odds of a strike on that roll. Press Enter to keep the default.

| On average | Seconds between rolls | Chance |
|---|---|---|
| once an hour (default) | `60` | `1/60` |
| once every 10 minutes | `60` | `1/10` |
| once a day | `60` | `1/1440` |
| once an hour, rolling every second | `1` | `1/3600` |

These are averages, so two strikes can land close together. To change them, run `python3 install.py install` again or edit `settings.json` in the install folder, then log back in so the runner picks up the change. Running `skeletor.py` from a checkout without `settings.json` uses the defaults at the top of the file.

## test

`python3 test_skeletor.py` checks the volume and dice logic without touching the real volume.

Plays it once, immediately.

```sh
python3 install.py run
```

After it is installed, the same thing from anywhere:

```sh
python3 "$HOME/.local/share/.skeletor/skeletor.py" --once
```

```powershell
python "$env:LOCALAPPDATA\.skeletor\skeletor.py" --once
```

## linux

```sh
#!/bin/sh
set -eu
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not installed"
  exit 1
fi
if [ -f ./install.py ] && [ -f ./skeletor.py ] && [ -f ./skeleton.mp4 ]; then
  exec python3 ./install.py < /dev/tty
fi
RAW="${RAW:-https://raw.githubusercontent.com/YOUR_USER/skeletor/main}"
d=$(mktemp -d)
cd "$d"
curl -fsSL "$RAW/install.py" -o install.py
curl -fsSL "$RAW/skeletor.py" -o skeletor.py
curl -fsSL "$RAW/skeleton.mp4" -o skeleton.mp4
exec python3 ./install.py < /dev/tty
```

## windows

```powershell
$ErrorActionPreference = "Stop"
$py = $null
foreach ($name in @("python", "py", "python3")) {
  $cmd = Get-Command $name -ErrorAction SilentlyContinue
  if ($cmd) { $py = $cmd.Source; break }
}
if (-not $py) { Write-Host "python is not installed"; exit 1 }
if ((Test-Path .\install.py) -and (Test-Path .\skeletor.py) -and (Test-Path .\skeleton.mp4)) {
  & $py .\install.py
  exit $LASTEXITCODE
}
$raw = if ($env:RAW) { $env:RAW } else { "https://raw.githubusercontent.com/YOUR_USER/skeletor/main" }
$dir = Join-Path $env:TEMP ("skeletor-" + [guid]::NewGuid().ToString("n"))
New-Item -ItemType Directory -Path $dir | Out-Null
foreach ($f in @("install.py", "skeletor.py", "skeleton.mp4")) {
  Invoke-WebRequest -Uri "$raw/$f" -OutFile (Join-Path $dir $f)
}
& $py (Join-Path $dir "install.py")
```

Set `RAW` if the repo is not `YOUR_USER/skeletor`.

## remove

### linux

```sh
rm -rf "$HOME/.local/share/.skeletor"
rm -f "$HOME/.config/autostart/skeletor.desktop"
```

### windows

```powershell
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "$env:LOCALAPPDATA\.skeletor"
Remove-Item -Force -ErrorAction SilentlyContinue "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\skeletor.cmd"
```

Same thing from the menu: `python3 install.py erase`. That also stops the runner if it is going.
