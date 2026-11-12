# Releasing VideoTagWriter

A release is a GitHub release `vX.Y.Z` with `VTW.exe` and its `.sha256` attached.
`release.ps1` does the checking, building and publishing. You only prepare the version and notes.

## 1. Prepare the version

1. **Bump the version** in `src/video_tag_writer/constants.py`: `APP_VERSION` and `APP_TIMESTAMP` (Central Time).
   Also update the version comment in `src/main.py` and `video-tag-writer.spec`.
2. **CHANGELOG.md**: add the entry. `release.ps1` refuses to run without it.
   ```
   ## VideoTagWriter [X.Y.Z] - YYYY-MM-DD HHMM CST
   ```
3. **README.md**: point the "Latest release" line at the new tag (`releases/tag/vX.Y.Z`).
   The script warns if you forget.
4. *(Optional)* **Hand-written notes**: create `notes/release/vX.Y.Z.md` with highlights.
   Without it, the release notes are the CHANGELOG section for X.Y.Z.
5. **Commit and push** everything. The script requires a clean tree in sync with `origin`.

## 2. Rehearse

```powershell
.\release.ps1 -DryRun
```

This runs every check and the full build (tests, PyInstaller, EXE self-test). It writes
`build\release_notes_vX.Y.Z.md` but publishes nothing. Read the notes file.

## 3. Publish

```powershell
.\release.ps1          # shows a summary, asks y/N before publishing
.\release.ps1 -Draft   # create as a draft; review it and press Publish on GitHub
```

Other options:

| Option | Effect |
|---|---|
| `-Yes` | Skip the y/N confirmation |
| `-SkipBuild` | Reuse the existing `dist\VTW.exe`. It must report the same version and be newer than the last commit |
| `-NotesFile path.md` | Use this file for the notes instead of `notes/release/` or the CHANGELOG |

## What the script checks (it stops on any failure)

- `gh` is installed and logged in
- The working tree is clean, and HEAD equals `origin/<branch>`
- Tag `vX.Y.Z` doesn't exist locally or on GitHub
- CHANGELOG.md has the `[X.Y.Z]` header
- The build passes: the full test suite, the PyInstaller build, and every EXE self-test check
- The EXE's embedded ProductVersion equals `APP_VERSION`

The tag is created on GitHub at the exact commit that was checked and built (`--target <sha>`).

## Manual fallback (no script)

```powershell
.\build_exe.ps1
(Get-FileHash dist\VTW.exe -Algorithm SHA256).Hash.ToLower()
gh release create vX.Y.Z dist\VTW.exe --repo juren53/video-tag-writer `
   --target master --title "VideoTagWriter vX.Y.Z" --notes-file <notes.md>
```

## Fixing a release

- **Notes wrong:** `gh release edit vX.Y.Z --repo juren53/video-tag-writer --notes-file new.md`
- **Bad EXE:** don't replace assets on a published release. Bump to `X.Y.Za` (the point-release convention) and release again.
- **Undo a release published by mistake:** `gh release delete vX.Y.Z --repo juren53/video-tag-writer --cleanup-tag`
