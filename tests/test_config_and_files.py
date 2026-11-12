"""Config persistence and file scanning."""

import json

from video_tag_writer.config import Config
from video_tag_writer.constants import DEFAULT_MODES, DEFAULT_DETECT_DEFAULT
from video_tag_writer.file_utils import get_video_files
from video_tag_writer.exiftool_utils import uses_sidecar, sidecar_path_for, tag_text, detect_mode


def test_config_uses_isolated_file(tmp_path):
    cfg = Config(config_file=str(tmp_path / 'c.json'))
    assert cfg.active_mode == DEFAULT_DETECT_DEFAULT
    assert set(DEFAULT_MODES) <= set(cfg.modes)


def test_config_roundtrip_keeps_custom_modes(tmp_path):
    path = str(tmp_path / 'c.json')
    cfg = Config(config_file=path)
    cfg.modes['Custom'] = [{"label": "X", "tag": "XMP-dc:Title", "widget": "line"}]
    cfg.active_mode = 'Custom'
    cfg.keep_backup = True
    cfg.save_config()

    again = Config(config_file=path)
    assert again.modes['Custom'][0]['tag'] == 'XMP-dc:Title'
    assert again.active_mode == 'Custom'
    assert again.keep_backup is True


def test_config_unknown_active_mode_falls_back(tmp_path):
    path = tmp_path / 'c.json'
    path.write_text(json.dumps({'active_mode': 'Gone'}), encoding='utf-8')
    assert Config(config_file=str(path)).active_mode == DEFAULT_DETECT_DEFAULT


def test_get_video_files_filters_and_sorts(tmp_path):
    for n in ('b.MP4', 'a.mpg', 'c.mpeg', 'd.m4v', 'notes.txt', 'e.xmp', 'f.mov'):
        (tmp_path / n).write_bytes(b'')
    names = [p.split('\\')[-1].split('/')[-1] for p in get_video_files(str(tmp_path))]
    assert names == ['a.mpg', 'b.MP4', 'c.mpeg', 'd.m4v']


def test_sidecar_helpers():
    assert uses_sidecar('x/clip.MPG') and uses_sidecar('clip.mpeg')
    assert not uses_sidecar('clip.mp4')
    assert sidecar_path_for('dir/clip.mpg').replace('\\', '/') == 'dir/clip.xmp'


def test_tag_text_and_detect_mode():
    tags = {'XMP-dc:Subject': ['a', 'b'], 'ItemList:TVSeason': 2, 'ItemList:Genre': ''}
    assert tag_text(tags, 'XMP-dc:Subject') == 'a; b'
    assert tag_text(tags, 'itemlist:tvseason') == '2'
    assert tag_text(tags, 'Missing:Tag') == ''
    frames = {"TV Episode": "ItemList:TVShow", "General": "ItemList:Genre", "Archival Video": ""}
    assert detect_mode(tags, frames, "Archival Video") == "Archival Video"   # empty Genre ignored
    assert detect_mode({'ItemList:TVShow': 'X'}, frames, "Archival Video") == "TV Episode"
    assert detect_mode(None, frames, "Archival Video") == "Archival Video"
