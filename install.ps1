# irm https://raw.githubusercontent.com/en1y/skeletor-prank/main/install.ps1 | iex
# In a script block with return, because exit would close the PowerShell window it runs in.
& {
    $ErrorActionPreference = "Stop"
    $raw = if ($env:RAW) { $env:RAW } else { "https://raw.githubusercontent.com/en1y/skeletor-prank/main" }

    # The Store's python.exe stub gets found but can't run, so each one has to prove it works.
    $py = $null
    foreach ($name in "py", "python", "python3") {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
        try { & $name -c "" 2>$null } catch { continue }
        if ($LASTEXITCODE -eq 0) { $py = $name; break }
    }
    if (-not $py) { Write-Host "python is not installed"; return }

    $dir = Join-Path $env:TEMP ("skeletor-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $dir | Out-Null
    try {
        foreach ($f in "install.py", "skeletor.py", "skeleton.mp4") {
            Invoke-WebRequest -UseBasicParsing -Uri "$raw/$f" -OutFile (Join-Path $dir $f)
        }
        & $py (Join-Path $dir "install.py") install
    } finally {
        Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue
    }
}
