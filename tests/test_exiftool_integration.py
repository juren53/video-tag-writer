"""
End-to-end tests against real ExifTool + ffmpeg-generated clips.
Skipped automatically when either tool is unavailable.
"""

import hashlib
import os
import shutil

import pytest

from video_tag_writer import exiftool_utils as et
from video_tag_writer.metadata import MetadataManager
from video_tag_writer.video_utils import get_video_info


def _md5(path):
    return hashlib.md5(open(path, 'rb').read()).hexdigest()


def _archival(values: dict) -> MetadataManager:
    m = MetadataManager()
    m.reload_mode('Archival Video')
    for k, v in values.items():
        m.set_field(k, v)
    return m


VALUES = {
    'Title': 'Truman Speech — Café',
    'Description': 'Line one\nLine two — ü',
    'Accession Number': 'SR59-230',
    'Speakers / People': 'Harry S. Truman; Dean Acheson',
    'Date Recorded': '1948-05-03',
    'Location': 'Independence, MO',
}


def test_mp4_roundtrip(clips):
    mp4 = clips['mp4']
    _archival(VALUES).save_to_file(mp4)

    file_tags, sidecar = et.read_metadata(mp4)
    assert sidecar is None
    assert file_tags['ItemList:Title'] == VALUES['Title']          # player-visible
    assert file_tags['XMP-dc:Title'] == VALUES['Title']            # archival
    assert file_tags['ItemList:Comment'] == VALUES['Description']  # description alias
    assert file_tags['XMP-dc:Contributor'] == ['Harry S. Truman', 'Dean Acheson']
    assert file_tags['ItemList:Artist'] == 'Harry S. Truman Library'

    reread = MetadataManager()
    reread.reload_mode('Archival Video')
    assert reread.load_from_file(mp4)
    for label, value in VALUES.items():
        assert reread.get_field(label) == value, label
    assert not os.path.exists(mp4 + '_original')   # no backup by default


def test_mp4_clearing_a_field_deletes_tags(clips):
    mp4 = clips['mp4']
    _archival(VALUES).save_to_file(mp4)
    m = _archival({**VALUES, 'Location': '', 'Title': ''})
    m.save_to_file(mp4)
    tags, _ = et.read_metadata(mp4)
    assert 'XMP-iptcCore:Location' not in tags
    assert 'ItemList:Title' not in tags and 'XMP-dc:Title' not in tags
    assert not any(str(v) == 'null' for v in tags.values())


def test_mp4_year_only_date(clips):
    mp4 = clips['mp4']
    _archival({'Date Recorded': '1948'}).save_to_file(mp4)
    tags, _ = et.read_metadata(mp4)
    assert str(tags['ItemList:ContentCreateDate']) == '1948'
    m = MetadataManager()
    m.reload_mode('Archival Video')
    m.load_from_file(mp4)
    assert m.get_field('Date Recorded') == '1948'


def test_mpg_writes_sidecar_and_leaves_video_untouched(clips):
    mpg = clips['mpg']
    before = _md5(mpg)
    plan = _archival(VALUES).save_to_file(mpg)

    sidecar = os.path.splitext(mpg)[0] + '.xmp'
    assert plan.sidecar and plan.target == sidecar and os.path.isfile(sidecar)
    assert _md5(mpg) == before

    side_tags = et.read_tags(sidecar)
    assert side_tags['XMP-dc:Title'] == VALUES['Title']
    assert not any(k.startswith('XMP-tiff') for k in side_tags)  # no copied tech tags

    m = MetadataManager()
    m.reload_mode('Archival Video')
    assert m.load_from_file(mpg)
    for label, value in VALUES.items():
        assert m.get_field(label) == value, label


def test_mpg_without_values_creates_no_sidecar(clips):
    mpg = clips['mpg']
    m = MetadataManager()
    m.reload_mode('General')          # General has no hidden auto-values
    plan = m.save_to_file(mpg)
    assert plan.empty
    assert not os.path.exists(os.path.splitext(mpg)[0] + '.xmp')


def test_unicode_filename(clips, tmp_path):
    mp4 = str(tmp_path / 'Café — clip.mp4')
    shutil.copy2(clips['mp4'], mp4)
    _archival({'Title': 'Ünïcode'}).save_to_file(mp4)
    tags, _ = et.read_metadata(mp4)
    assert tags['ItemList:Title'] == 'Ünïcode'


def test_cover_art_roundtrip(clips, tmp_path):
    from video_tag_writer.video_utils import extract_poster_frame
    png = extract_poster_frame(clips['mp4'], 2.0)
    if not png:
        pytest.skip("ffmpeg poster extraction unavailable")
    img = tmp_path / 'art.png'
    img.write_bytes(png)
    et.write_cover_art(clips['mp4'], str(img))
    art = et.read_cover_art(clips['mp4'])
    assert art and art[:8] == b'\x89PNG\r\n\x1a\n'
    et.remove_cover_art(clips['mp4'])
    assert et.read_cover_art(clips['mp4']) is None


def test_technical_info(clips):
    for kind in ('mp4', 'mpg'):
        info = get_video_info(clips[kind], et.read_tags(clips[kind]))
        assert info['resolution'] == '320 × 240', kind
        assert info['duration'] != '--', kind
        assert '25' in info['frame_rate'], kind


def test_all_tags_listing(clips):
    rows = et.read_all_tags_listing(clips['mp4'])
    assert any(group == 'File' and tag == 'FileType' for group, tag, _ in rows)


def test_music_mode_roundtrip_mp4(clips):
    from video_tag_writer.constants import DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT
    values = {'Song Title': 'Ünder Pressure', 'Artist': 'Queen; David Bowie', 'Album': 'Hot Space',
              'Track': '11 of 11', 'Year': '1981', 'Genre': 'Rock', 'Record Label': 'EMI',
              'Lyrics': 'Pressure\npushing down on me', 'Director': 'David Mallet'}
    m = MetadataManager()
    m.reload_mode('Music')
    for k, v in values.items():
        m.set_field(k, v)
    m.save_to_file(clips['mp4'])

    tags, _ = et.read_metadata(clips['mp4'])
    assert tags['ItemList:MediaType'] == 'Music Video'
    assert tags['ItemList:TrackNumber'] == '11 of 11'
    assert tags['XMP-xmpDM:TrackNumber'] == 11
    assert et.detect_mode(tags, DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT) == 'Music'

    back = MetadataManager()
    back.reload_mode('Music')
    back.load_from_file(clips['mp4'])
    for label, value in values.items():
        assert back.get_field(label) == value, label


def test_movie_mode_mpg_sidecar_detects(clips):
    from video_tag_writer.constants import DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT
    m = MetadataManager()
    m.reload_mode('Movie')
    m.set_field('Title', 'The Truman Story')
    m.set_field('Director', 'A. Director')
    m.set_field('Genre', 'Documentary')
    m.save_to_file(clips['mpg'])
    _, side = et.read_metadata(clips['mpg'])
    assert side['XMP-xmpDM:Director'] == 'A. Director'
    assert et.detect_mode(side, DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT) == 'Movie'


def test_tv_media_type_value_is_valid(clips):
    m = MetadataManager()
    m.reload_mode('TV Episode')
    m.set_field('Title', 'Pilot')
    m.save_to_file(clips['mp4'])
    tags, _ = et.read_metadata(clips['mp4'])
    assert tags['ItemList:MediaType'] == 'TV Show'   # ExifTool refuses unknown values


def test_detect_mode_with_real_tags(clips):
    m = MetadataManager()
    m.reload_mode('TV Episode')
    m.set_field('Show', 'Meet the Press')
    m.save_to_file(clips['mp4'])
    tags, _ = et.read_metadata(clips['mp4'])
    frames = {"TV Episode": "ItemList:TVShow", "General": "ItemList:Genre", "Archival Video": ""}
    assert et.detect_mode(tags, frames, "Archival Video") == "TV Episode"
