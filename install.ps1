# irm https://raw.githubusercontent.com/en1y/skeletor-prank/main/install.ps1 | iex
# In a script block with return, because exit would close the PowerShell window it runs in.
& {
    $ErrorActionPreference = "Stop"
    $raw = if ($env:RAW) { $env:RAW } else { "https://raw.githubusercontent.com/en1y/skeletor-prank/main" }

    # A window opened before Python was installed still has the old PATH.
    $env:Path += ";" + [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
    # The python.org installer can leave Python off PATH, but it always registers it here.
    $keys = "HKCU:\Software\Python\PythonCore\*\InstallPath", "HKLM:\Software\Python\PythonCore\*\InstallPath", "HKLM:\Software\WOW6432Node\Python\PythonCore\*\InstallPath"
    $registered = @(Get-ItemProperty $keys -ErrorAction SilentlyContinue | ForEach-Object { $_.ExecutablePath } | Where-Object { $_ })

    # The Store's python.exe stub gets found but can't run, so each one has to prove it works.
    # Not -c "", because Windows PowerShell drops empty arguments and every Python then fails.
    $py = $null
    foreach ($name in @("py", "python", "python3") + $registered) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
        try { & $name -c "pass" 2>$null } catch { continue }
        if ($LASTEXITCODE -eq 0) { $py = $name; break }
    }
    if (-not $py) { Write-Host "python was not found. install it from https://www.python.org/downloads/ and run this again"; return }

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
