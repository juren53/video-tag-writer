"""Movie / Music modes, track numbers, value-based detection rules, config migration."""

import pytest

from video_tag_writer.config import merge_detect_frames
from video_tag_writer.constants import DEFAULT_MODES, DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT
from video_tag_writer.exiftool_utils import rule_matches, detect_mode
from video_tag_writer.metadata import (
    MetadataManager, parse_track, track_tag_value, storable_in_sidecar,
)


def _mgr(mode):
    m = MetadataManager()
    m.reload_mode(mode)
    return m


# -- track numbers ----------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("3", (3, None)), ("3 of 12", (3, 12)), ("3/12", (3, 12)), (" 3 OF 12 ", (3, 12)),
])
def test_parse_track_valid(value, expected):
    assert parse_track(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "0", "5 of 3", "3-12", "three"])
def test_parse_track_invalid(value):
    with pytest.raises(ValueError):
        parse_track(value)


def test_track_tag_value_per_group():
    assert track_tag_value("ItemList:TrackNumber", "3/12") == ("ItemList:TrackNumber", "3 of 12")
    assert track_tag_value("ItemList:TrackNumber", "3") == ("ItemList:TrackNumber", "3")
    assert track_tag_value("XMP-xmpDM:TrackNumber", "3 of 12") == ("XMP-xmpDM:TrackNumber", 3)


# -- detection rules --------------------------------------------------------

def test_rule_matches_forms():
    tags = {'ItemList:MediaType': 'Music Video', 'XMP-dc:Type': ['Movie'], 'ItemList:TVShow': 'X'}
    assert rule_matches(tags, 'ItemList:TVShow')
    assert rule_matches(tags, 'ItemList:MediaType=music video')        # case-insensitive
    assert not rule_matches(tags, 'ItemList:MediaType=Movie')
    assert rule_matches(tags, 'ItemList:MediaType=Movie|XMP-dc:Type=Movie')  # alternative
    assert rule_matches(tags, 'XMP-dc:Type=Movie')                      # list tag
    assert not rule_matches(tags, '')
    assert not rule_matches({}, 'ItemList:TVShow')


def test_movie_and_music_beat_general():
    # Movie/Music files also carry Genre, which is the General rule
    movie = {'ItemList:MediaType': 'Movie', 'ItemList:Genre': 'Drama'}
    music = {'ItemList:MediaType': 'Music Video', 'ItemList:Genre': 'Rock'}
    general = {'ItemList:Genre': 'Home Video'}
    f, d = DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT
    assert detect_mode(movie, f, d) == 'Movie'
    assert detect_mode(music, f, d) == 'Music'
    assert detect_mode(general, f, d) == 'General'
    assert detect_mode({}, f, d) == 'Archival Video'


def test_sidecar_tags_detect_mode():
    # MPG sidecars only hold XMP — the XMP-dc:Type alternative makes detection work
    f, d = DEFAULT_DETECT_FRAMES, DEFAULT_DETECT_DEFAULT
    assert detect_mode({'XMP-dc:Type': ['Music Video']}, f, d) == 'Music'
    assert detect_mode({'XMP-dc:Type': ['Movie']}, f, d) == 'Movie'
    assert detect_mode({'XMP-dc:Type': ['TV Show']}, f, d) == 'TV Episode'


# -- config migration -------------------------------------------------------

def test_merge_detect_frames_from_v010_config():
    v010 = {"TV Episode": "ItemList:TVShow", "General": "ItemList:Genre", "Archival Video": ""}
    merged = merge_detect_frames(v010)
    assert list(merged) == list(DEFAULT_DETECT_FRAMES)          # Movie/Music before General
    assert merged["TV Episode"] == DEFAULT_DETECT_FRAMES["TV Episode"]   # legacy rule upgraded


def test_merge_detect_frames_keeps_custom_and_user_edits():
    saved = {"Lecture": "XMP-dc:Type=Lecture", "General": "ItemList:Album"}
    merged = merge_detect_frames(saved)
    assert list(merged)[0] == "Lecture"                         # custom first
    assert merged["General"] == "ItemList:Album"               # user edit kept
    assert merge_detect_frames(None) == DEFAULT_DETECT_FRAMES


# -- mode specs / write plans -----------------------------------------------

@pytest.mark.parametrize("mode,mp4_only", [
    ("Movie", {"Producer"}),
    ("Music", {"Album Artist"}),
])
def test_sidecar_coverage(mode, mp4_only):
    blocked = {s['label'] for s in DEFAULT_MODES[mode]
               if s.get('widget') != 'hidden' and not storable_in_sidecar(s)}
    assert blocked == mp4_only


def test_music_plan_embedded():
    m = _mgr('Music')
    m.set_field('Song Title', 'Give Me Your Love')
    m.set_field('Track', '3/12')
    m.set_field('Year', '1975')
    plan = m.build_write_plan('x.mp4')
    sv = plan.set_values
    assert sv['ItemList:TrackNumber'] == '3 of 12'
    assert sv['XMP-xmpDM:TrackNumber'] == 3
    assert sv['ItemList:ContentCreateDate#'] == '1975'
    assert sv['ItemList:MediaType'] == 'Music Video' and sv['XMP-dc:Type'] == 'Music Video'


def test_movie_plan_sidecar():
    m = _mgr('Movie')
    m.set_field('Title', 'Mr. Smith')
    m.set_field('Producer', 'Frank Capra')
    plan = m.build_write_plan('x.mpg')
    assert plan.skipped == ['Producer']
    assert plan.set_values['XMP-dc:Type'] == 'Movie'
    assert 'ItemList:MediaType' not in plan.set_values


def test_music_validate_track():
    m = _mgr('Music')
    m.set_field('Track', 'side B')
    assert any('Track' in p for p in m.validate())
