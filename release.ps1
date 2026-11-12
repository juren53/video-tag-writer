# Video Tag Writer - GitHub release script
#
# Publishes the version in src/video_tag_writer/constants.py (APP_VERSION) as a GitHub
# release "vX.Y.Z" with dist\VTW.exe (+ a .sha256 file) attached.
#
# Usage:
#   .\release.ps1 -DryRun        # run every check and build, write the notes, publish nothing
#   .\release.ps1                # build, check, show summary, ask before publishing
#   .\release.ps1 -Yes           # same, without the confirmation prompt
#   .\release.ps1 -SkipBuild     # reuse the existing dist\ EXE (its version must match)
#   .\release.ps1 -Draft         # create the release as a draft (publish later on GitHub)
#   .\release.ps1 -NotesFile x.md
#
# Release notes = notes/release/vX.Y.Z.md if present (hand-written highlights),
# otherwise the CHANGELOG.md section for X.Y.Z; a Download section (size, SHA-256,
# bundled ExifTool version) is always appended.
#
# Full procedure: docs/RELEASING.md

param(
    [switch]$DryRun,
    [switch]$SkipBuild,
    [switch]$Draft,
    [switch]$Yes,
    [string]$NotesFile = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Repo      = "juren53/video-tag-writer"
$ExePath   = Join-Path $Root "dist\VTW.exe"
$SelfTest  = Join-Path $Root "build\selftest.json"

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "  [ OK ] $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "RELEASE STOPPED: $msg" -ForegroundColor Red; exit 1 }

function Invoke-Git {
    # Local "Continue": under Windows PowerShell 5.1 + Stop, git's stderr would abort the script
    $ErrorActionPreference = "Continue"
    $out = & git.exe @args 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { Fail "git $args failed:`n$($out -join "`n")" }
    return $out
}

# ── Version ──────────────────────────────────────────────────────
$constants = Get-Content "src\video_tag_writer\constants.py" -Raw -Encoding UTF8
if ($constants -notmatch '(?m)^APP_VERSION\s*=\s*"([^"]+)"') { Fail "APP_VERSION not found in constants.py" }
$Version = $Matches[1]
$Tag = "v$Version"
Write-Host "Releasing Video Tag Writer $Tag" -ForegroundColor White

# ── Pre-flight checks ────────────────────────────────────────────
Step "Pre-flight checks"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Fail "GitHub CLI (gh) not found. Install from https://cli.github.com" }
& gh auth status *> $null
if ($LASTEXITCODE -ne 0) { Fail "gh is not logged in. Run: gh auth login" }
Ok "gh installed and authenticated"

$dirty = Invoke-Git status --porcelain
if ($dirty) { Fail "Working tree has uncommitted changes:`n$($dirty -join "`n")`nCommit or stash them first." }
Ok "working tree clean"

$branch = (Invoke-Git rev-parse --abbrev-ref HEAD).Trim()
Invoke-Git fetch --quiet origin | Out-Null
$local  = (Invoke-Git rev-parse HEAD).Trim()
$remote = (& git rev-parse "origin/$branch" 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $remote) { Fail "Branch '$branch' has no origin/$branch. Push it first." }
if ($local -ne $remote.Trim()) { Fail "HEAD ($($local.Substring(0,7))) differs from origin/$branch. Push or pull first." }
Ok "branch '$branch' in sync with origin ($($local.Substring(0,7)))"
if ($branch -ne "master") { Write-Host "  [WARN] releasing from '$branch', not master" -ForegroundColor Yellow }

if (& git tag --list $Tag) { Fail "Tag $Tag already exists locally. Bump APP_VERSION for a new release." }
& gh release view $Tag --repo $Repo *> $null
if ($LASTEXITCODE -eq 0) { Fail "Release $Tag already exists on GitHub." }
Ok "tag/release $Tag not used yet"

$changelog = Get-Content "CHANGELOG.md" -Raw -Encoding UTF8
$hdr = "(?m)^## Video Tag Writer \[" + [regex]::Escape($Version) + "\] - .+$"
if ($changelog -notmatch $hdr) { Fail "CHANGELOG.md has no '## Video Tag Writer [$Version] - YYYY-MM-DD HHMM CST' header." }
Ok "CHANGELOG.md has a $Version entry"

$readme = Get-Content "README.md" -Raw -Encoding UTF8
if ($readme -notmatch [regex]::Escape("releases/tag/$Tag")) {
    Write-Host "  [WARN] README.md 'Latest release' does not link $Tag" -ForegroundColor Yellow
}

# ── Build (tests + EXE + self-test) ──────────────────────────────
if ($SkipBuild) {
    Step "Using existing EXE (-SkipBuild)"
    if (-not (Test-Path $ExePath)) { Fail "$ExePath not found. Run without -SkipBuild." }
} else {
    Step "Building (build_exe.ps1: tests, PyInstaller, self-test)"
    & (Join-Path $Root "build_exe.ps1")
    if ($LASTEXITCODE -ne 0) { Fail "build_exe.ps1 failed." }
}

$exeVersion = (Get-Item $ExePath).VersionInfo.ProductVersion
if ($exeVersion -ne $Version) { Fail "EXE ProductVersion is '$exeVersion', expected '$Version'. Rebuild." }
Ok "EXE version $exeVersion"

$exeTime = (Get-Item $ExePath).LastWriteTime
$commitTime = [DateTime]::Parse((Invoke-Git log -1 --format=%cI).Trim())
if ($exeTime -lt $commitTime) { Fail "EXE is older than the last commit. Rebuild (omit -SkipBuild)." }

# ── Release notes ────────────────────────────────────────────────
Step "Preparing release notes"
$hash = (Get-FileHash $ExePath -Algorithm SHA256).Hash.ToLower()
$sizeMB = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
$exiftoolVer = "bundled"
if (Test-Path $SelfTest) {
    $st = Get-Content $SelfTest -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($st.info.exiftool) { $exiftoolVer = ($st.info.exiftool -split '\s+')[0] }
}

$highlights = Join-Path $Root "notes\release\$Tag.md"
if ($NotesFile) {
    if (-not (Test-Path $NotesFile)) { Fail "Notes file not found: $NotesFile" }
    $body = Get-Content $NotesFile -Raw -Encoding UTF8
    $source = $NotesFile
} elseif (Test-Path $highlights) {
    $body = Get-Content $highlights -Raw -Encoding UTF8
    $source = "notes\release\$Tag.md"
} else {
    # CHANGELOG section: from this version's header up to the next '## ' header
    $m = [regex]::Match($changelog, "$hdr\r?\n(?<s>[\s\S]*?)(?=\r?\n## |\z)")
    $body = $m.Groups['s'].Value.Trim()
    $source = "CHANGELOG.md"
}

$notes = @"
$($body.Trim())

### Download
``VTW.exe`` is a single-file Windows executable ($sizeMB MB) with **ExifTool $exiftoolVer bundled**. No install is needed.
- **Optional:** with **ffmpeg/ffprobe** on your PATH you also get poster frames and fuller technical info.
- SHA-256: ``$hash`` (also attached as ``VTW.exe.sha256``)

Full details: [CHANGELOG.md](https://github.com/$Repo/blob/$Tag/CHANGELOG.md)
"@

New-Item -ItemType Directory -Force -Path (Join-Path $Root "build") | Out-Null
$notesOut = Join-Path $Root "build\release_notes_$Tag.md"
$shaOut   = Join-Path $Root "build\VTW.exe.sha256"
[IO.File]::WriteAllText($notesOut, $notes, (New-Object Text.UTF8Encoding $false))
[IO.File]::WriteAllText($shaOut, "$hash  VTW.exe`n", (New-Object Text.UTF8Encoding $false))
Ok "notes from $source  ->  build\release_notes_$Tag.md"

# ── Summary / confirm ────────────────────────────────────────────
Step "Summary"
Write-Host "  Release : $Tag  ($(if ($Draft) {'draft'} else {'public'}))"
Write-Host "  Commit  : $local  ($branch)"
Write-Host "  Asset   : VTW.exe  $sizeMB MB"
Write-Host "  SHA-256 : $hash"
Write-Host "  Notes   : $notesOut"

if ($DryRun) {
    Write-Host "`nDry run complete. Nothing was published." -ForegroundColor Yellow
    exit 0
}
if (-not $Yes) {
    $answer = Read-Host "`nPublish $Tag to https://github.com/$Repo ? (y/N)"
    if ($answer -notmatch '^(y|yes)$') { Write-Host "Cancelled. Nothing was published."; exit 0 }
}

# ── Publish ──────────────────────────────────────────────────────
Step "Publishing"
$ghArgs = @("release", "create", $Tag, $ExePath, $shaOut,
          "--repo", $Repo, "--target", $local,
          "--title", "Video Tag Writer $Tag", "--notes-file", $notesOut)
if ($Draft) { $ghArgs += "--draft" }
& gh @ghArgs
if ($LASTEXITCODE -ne 0) { Fail "gh release create failed." }

Invoke-Git fetch --quiet --tags origin | Out-Null
$url = (& gh release view $Tag --repo $Repo --json url --jq .url)
Write-Host "`nReleased: $url" -ForegroundColor Green
