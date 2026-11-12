"""
Generate version_info.txt for the PyInstaller Windows EXE Properties/Details tab.
Run before building: python generate_version_info.py   (build_exe.ps1 does this)
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
CONSTANTS_PATH = os.path.join(HERE, 'src', 'video_tag_writer', 'constants.py')
OUTPUT_PATH = os.path.join(HERE, 'version_info.txt')


def read_constant(name: str) -> str:
    with open(CONSTANTS_PATH, encoding='utf-8') as f:
        text = f.read()
    m = re.search(rf'^{name}\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if not m:
        raise RuntimeError(f"{name} not found in constants.py")
    return m.group(1)


def version_tuple(v: str) -> tuple:
    """'0.7.14a' -> (0, 7, 14, 0)"""
    parts = [int(re.sub(r'[^0-9].*$', '', x) or 0) for x in v.split('.')]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def write_version_info(version: str, org: str):
    vt = version_tuple(version)
    year = read_constant('APP_TIMESTAMP')[:4]
    content = f"""\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vt},
    prodvers={vt},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [StringStruct(u'CompanyName',      u'{org}'),
           StringStruct(u'FileDescription',  u'Video Tag Writer'),
           StringStruct(u'FileVersion',      u'{version}'),
           StringStruct(u'InternalName',     u'video-tag-writer'),
           StringStruct(u'LegalCopyright',   u'Copyright (c) {year} {org}'),
           StringStruct(u'OriginalFilename', u'video-tag-writer.exe'),
           StringStruct(u'ProductName',      u'Video Tag Writer'),
           StringStruct(u'ProductVersion',   u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
"""
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"version_info.txt written  ({version} -> {vt})")


if __name__ == '__main__':
    write_version_info(read_constant('APP_VERSION'), read_constant('APP_ORGANIZATION'))
