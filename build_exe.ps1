# Video Tag Writer - PyInstaller build script
#
# Usage:
#   .\build_exe.ps1                       # standard build (bundles ExifTool)
#   .\build_exe.ps1 -IncludeFFmpeg        # also bundle ffmpeg + ffprobe (~100+ MB larger)
#   .\build_exe.ps1 -ExifTool C:\path\exiftool.exe
#   .\build_exe.ps1 -SkipTests            # skip the pytest gate
#
# Output: dist\video-tag-writer.exe, verified by running "--self-test" on the built EXE.

param(
    [switch]$IncludeFFmpeg,
    [string]$ExifTool = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$VenvDir    = Join-Path $ScriptDir "venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$SpecFile   = Join-Path $ScriptDir "video-tag-writer.spec"
$ExePath    = Join-Path $ScriptDir "dist\video-tag-writer.exe"

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "BUILD FAILED: $msg" -ForegroundColor Red; exit 1 }

# ── Virtual environment ──────────────────────────────────────────
if (-not (Test-Path $VenvPython)) {
    Step "Creating virtual environment"
    $py = Get-Command py -ErrorAction SilentlyContinue
    if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
    if (-not $py) { Fail "No Python found. Install Python 3.10+ from https://python.org" }
    & $py.Source -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { Fail "Could not create venv." }
}

Step "Installing dependencies + PyInstaller"
& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -r requirements.txt pyinstaller --quiet
if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }
New-Item -ItemType File -Path (Join-Path $VenvDir ".deps_installed") -Force | Out-Null

# ── ExifTool to bundle ───────────────────────────────────────────
if ($ExifTool) {
    if (-not (Test-Path $ExifTool)) { Fail "ExifTool not found at $ExifTool" }
    $env:VTW_EXIFTOOL = (Resolve-Path $ExifTool).Path
} else {
    Remove-Item Env:\VTW_EXIFTOOL -ErrorAction SilentlyContinue
}
$env:VTW_BUNDLE_FFMPEG = if ($IncludeFFmpeg) { "1" } else { "0" }

# ── Test gate ────────────────────────────────────────────────────
if (-not $SkipTests) {
    Step "Running tests"
    & $VenvPython -m pytest tests -q -p no:cacheprovider
    if ($LASTEXITCODE -ne 0) { Fail "Tests failed (use -SkipTests to override)." }
}

# ── Version resource ─────────────────────────────────────────────
Step "Generating version_info.txt"
& $VenvPython generate_version_info.py
if ($LASTEXITCODE -ne 0) { Fail "generate_version_info.py failed." }

# ── Clean ────────────────────────────────────────────────────────
foreach ($dir in @("build", "dist")) {
    $full = Join-Path $ScriptDir $dir
    if (Test-Path $full) {
        Write-Host "Removing $dir\ ..."
        Remove-Item -Recurse -Force $full
    }
}

# ── Build ────────────────────────────────────────────────────────
Step "Running PyInstaller"
& $VenvPython -m PyInstaller $SpecFile --noconfirm
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller exited with code $LASTEXITCODE." }
if (-not (Test-Path $ExePath)) { Fail "PyInstaller reported success but $ExePath is missing." }

# ── Self-test the frozen EXE ─────────────────────────────────────
# Catches what PyInstaller's static analysis can miss (e.g. ATW v0.7.14a shipped
# without theme_manager): imports, bundled ExifTool, version resource, docs.
Step "Self-testing the EXE"
$Report = Join-Path $ScriptDir "build\selftest.json"
Remove-Item $Report -ErrorAction SilentlyContinue
$proc = Start-Process -FilePath $ExePath -ArgumentList @("--self-test", "`"$Report`"") `
                      -Wait -PassThru -WindowStyle Hidden
if (-not (Test-Path $Report)) {
    Fail "Self-test produced no report (exit $($proc.ExitCode)) — the EXE probably crashed at startup. Rebuild with console=True in the spec to see the traceback."
}
$result = Get-Content $Report -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($check in $result.checks.PSObject.Properties) {
    $mark = if ($check.Value) { "[ OK ]" } else { "[FAIL]" }
    $color = if ($check.Value) { "Green" } else { "Red" }
    Write-Host ("  {0} {1}" -f $mark, $check.Name) -ForegroundColor $color
}
foreach ($item in $result.info.PSObject.Properties) {
    Write-Host ("         {0}: {1}" -f $item.Name, $item.Value) -ForegroundColor DarkGray
}
if (-not $result.passed) { Fail "Self-test checks failed — see $Report" }

# ── Done ─────────────────────────────────────────────────────────
$Size = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
$ff = if ($IncludeFFmpeg) { "with ffmpeg/ffprobe" } else { "ExifTool only; ffmpeg used from PATH if present" }
Write-Host "`nBuild succeeded: $ExePath  ($Size MB, $ff)" -ForegroundColor Green
