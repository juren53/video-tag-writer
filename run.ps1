# VideoTagWriter launcher — creates/validates venv, installs deps, runs app.

$ErrorActionPreference = "Stop"

# --- CONFIGURATION ---
$AppName      = "VideoTagWriter"
$EntryPoint   = "src\main.py"
$VenvDir      = "venv"
$Requirements = "requirements.txt"
# --- END CONFIGURATION ---

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Test-VenvValid {
    param([string]$VenvPath)
    $cfg = Join-Path $VenvPath "pyvenv.cfg"
    if (-not (Test-Path $cfg)) { return $false }
    $homeLine = Get-Content $cfg | Where-Object { $_ -match "^home\s*=" }
    if (-not $homeLine) { return $false }
    $pythonHome = ($homeLine -split "=", 2)[1].Trim()
    return (Test-Path (Join-Path $pythonHome "python.exe"))
}

function Find-Python {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        try { $null = & py --version 2>&1; if ($LASTEXITCODE -eq 0) { return "py" } } catch {}
    }
    $searchPatterns = @(
        "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
        "C:\Python3*\python.exe",
        "C:\Python*\python.exe"
    )
    foreach ($pattern in $searchPatterns) {
        $candidate = Get-Item $pattern -ErrorAction SilentlyContinue |
                     Sort-Object Name -Descending | Select-Object -First 1
        if ($candidate) {
            try { $null = & $candidate.FullName --version 2>&1; if ($LASTEXITCODE -eq 0) { return $candidate.FullName } } catch {}
        }
    }
    foreach ($cmd in @("python", "python3")) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            try { $null = & $found.Source --version 2>&1; if ($LASTEXITCODE -eq 0) { return $found.Source } } catch {}
        }
    }
    return $null
}

if ((Test-Path $VenvDir) -and -not (Test-VenvValid $VenvDir)) {
    Write-Host "[$AppName] Existing venv has a broken Python reference, recreating..."
    Remove-Item $VenvDir -Recurse -Force
}

if (-not (Test-Path $VenvDir)) {
    Write-Host "[$AppName] Creating virtual environment..."
    $pythonExe = Find-Python
    if (-not $pythonExe) {
        Write-Error "Error: no working Python found. Install Python from https://python.org"
        exit 1
    }
    Write-Host "[$AppName] Using Python: $pythonExe"
    & $pythonExe -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Write-Error "Error: Failed to create venv."; exit 1 }
}

$ActivateScript = "$VenvDir\Scripts\Activate.ps1"
if (Test-Path $ActivateScript) { & $ActivateScript }
else { Write-Error "Error: cannot find venv activate script"; exit 1 }

$Marker = "$VenvDir\.deps_installed"
$installDeps = $false
if (-not (Test-Path $Marker)) { $installDeps = $true }
elseif ((Get-Item $Requirements).LastWriteTime -gt (Get-Item $Marker).LastWriteTime) { $installDeps = $true }

if ($installDeps) {
    Write-Host "[$AppName] Installing dependencies..."
    python -m pip install --upgrade pip -q
    pip install -r $Requirements -q
    New-Item -ItemType File -Path $Marker -Force | Out-Null
}

python $EntryPoint @args
