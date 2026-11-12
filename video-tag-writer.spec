# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for VideoTagWriter
# Build: .\build_exe.ps1   (or: pyinstaller video-tag-writer.spec)
# Version: 0.2.1
#
# Environment variables read at build time:
#   VTW_EXIFTOOL        path to exiftool.exe to bundle (default: PATH, then ~/bin)
#   VTW_BUNDLE_FFMPEG   "1" to also bundle ffmpeg.exe + ffprobe.exe (adds ~100+ MB;
#                       without them the EXE still works and uses any ffmpeg on PATH)

import os
import shutil
import sys

block_cipher = None
SPEC_DIR = os.path.abspath(SPECPATH)

# ── Shared modules (runtime sys.path insertions — invisible to PyInstaller) ──────────
# Same lesson as ATW v0.7.14a: without these on pathex the modules are silently left
# out of the exe, which then crashes at startup on any other machine.
THEME_MANAGER_PATH = os.path.expanduser('~/Projects/ThemeManager')
IMM_PATH = os.path.expanduser('~/Projects/Icon_Manager_Module')
for _required in (os.path.join(THEME_MANAGER_PATH, 'theme_manager'),
                  os.path.join(IMM_PATH, 'icon_loader.py')):
    if not os.path.exists(_required):
        raise SystemExit(f'{_required} not found — required for the build.')


# ── ExifTool (required) ───────────────────────────────────────────────────────────────
def _find_exiftool():
    candidates = [os.environ.get('VTW_EXIFTOOL'), shutil.which('exiftool'),
                  os.path.expanduser('~/bin/exiftool.exe')]
    for c in candidates:
        if c and os.path.isfile(c):
            return os.path.abspath(c)
    raise SystemExit('exiftool.exe not found — set VTW_EXIFTOOL or put it on PATH.')


EXIFTOOL = _find_exiftool()
if os.path.basename(EXIFTOOL).lower() != 'exiftool.exe':
    # The app looks for exactly 'exiftool.exe' in the bundle (exiftool_utils.find_exiftool).
    raise SystemExit(f'{EXIFTOOL}: rename it to exiftool.exe before building '
                     '(the download is named "exiftool(-k).exe").')
print(f'[spec] Bundling ExifTool: {EXIFTOOL}')

binaries = [(EXIFTOOL, '.')]
datas = [
    ('CHANGELOG.md', '.'),
    ('README.md', '.'),
]
if os.listdir(os.path.join(SPEC_DIR, 'resources', 'icons')) != ['.gitkeep']:
    datas.append(('resources/icons', 'resources/icons'))

# ExifTool >= 12.88 Windows packages ship a Perl runtime folder beside the exe.
_exiftool_files = os.path.join(os.path.dirname(EXIFTOOL), 'exiftool_files')
if os.path.isdir(_exiftool_files):
    datas.append((_exiftool_files, 'exiftool_files'))
    print(f'[spec] Bundling {_exiftool_files}')


# ── ffmpeg / ffprobe (optional) ────────────────────────────────────────────────────────
if os.environ.get('VTW_BUNDLE_FFMPEG') == '1':
    sys.path.insert(0, os.path.join(SPEC_DIR, 'src'))
    from video_tag_writer.video_utils import find_ff_tools   # picks the newest build on PATH
    _ffmpeg, _ffprobe = find_ff_tools('')
    if not (_ffmpeg and _ffprobe):
        raise SystemExit('VTW_BUNDLE_FFMPEG=1 but ffmpeg/ffprobe were not found on PATH.')
    binaries += [(_ffmpeg, '.'), (_ffprobe, '.')]
    print(f'[spec] Bundling ffmpeg:  {_ffmpeg}\n[spec] Bundling ffprobe: {_ffprobe}')


_icon = os.path.join(SPEC_DIR, 'assets', 'ICON_vtw.ico')
_icon = _icon if os.path.isfile(_icon) else None
if _icon is None:
    print('[spec] assets/ICON_vtw.ico not found — EXE will use the default icon.')

a = Analysis(
    ['src/main.py'],
    pathex=['src', THEME_MANAGER_PATH, IMM_PATH],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'exiftool',              # PyExifTool — imported lazily inside get_helper()
        'theme_manager',
        'icon_loader',
        'pyqt_app_info',
        'pyqt_app_info.qt',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt6.QtWebEngineCore', 'PyQt6.QtWebEngineWidgets',
              'PyQt6.Qt3DCore', 'PyQt6.QtQuick', 'PyQt6.QtQml'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VTW',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # Never UPX-compress the bundled tools: exiftool.exe is a self-extracting Perl
    # archive and ffmpeg builds don't tolerate repacking.
    upx_exclude=['exiftool.exe', 'ffmpeg.exe', 'ffprobe.exe', 'vcruntime140.dll',
                 'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll'],
    # Extract under %LOCALAPPDATA% rather than a CWD-relative dir: Explorer's
    # "Open with" can set the CWD to a read-only or network folder (ATW issue #6).
    runtime_tmpdir=r'%LOCALAPPDATA%\video-tag-writer\runtime',
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
    version='version_info.txt',
)
