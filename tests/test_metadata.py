"""MetadataManager unit tests — no ExifTool needed (write plans are pure)."""

import json
import os

import pytest

from video_tag_writer.constants import APP_NAME, APP_VERSION, DEFAULT_MODES
from video_tag_writer.metadata import MetadataManager, field_tags, storable_in_sidecar


@pytest.fixture
def mgr():
    m = MetadataManager()
    m.reload_mode('Archival Video')
    return m


# -- sanitize ---------------------------------------------------------------

def test_sanitize(mgr):
    assert mgr._sanitize_value('  hi\x00 ') == 'hi'
    assert mgr._sanitize_value('a\r\nb\rc') == 'a\nb\nc'
    assert len(mgr._sanitize_value('x' * 3000, 2000)) == 2000
    assert mgr._sanitize_value(None) == ''


# -- mode specs -------------------------------------------------------------

def test_every_archival_field_survives_in_sidecar():
    for spec in DEFAULT_MODES['Archival Video']:
        if spec.get('widget') != 'hidden':
            assert storable_in_sidecar(spec), spec['label']


def test_specs_use_group_qualified_tags():
    for mode, specs in DEFAULT_MODES.items():
        for spec in specs:
            for tag in field_tags(spec):
                assert ':' in tag, f"{mode}/{spec['label']}: {tag}"


# -- read -------------------------------------------------------------------

def test_load_from_tags_alias_fallback_lists_and_dates(mgr):
    tags = {
        'XMP-dc:Title': 'From XMP',                         # primary ItemList:Title absent
        'XMP-dc:Contributor': ['Truman', 'Acheson'],
        'ItemList:ContentCreateDate': '1948:05:03 00:00:00-06:00',  # alias of XMP-dc:Date
        'ItemList:Comment': 'desc via comment',             # alias of Description
    }
    mgr.load_from_tags('x.mp4', tags)
    assert mgr.get_field('Title') == 'From XMP'
    assert mgr.get_field('Speakers / People') == 'Truman; Acheson'
    assert mgr.get_field('Date Recorded') == '1948-05-03'
    assert mgr.get_field('Description') == 'desc via comment'
    assert mgr.get_field('Location') == ''


def test_primary_wins_over_alias(mgr):
    mgr.load_from_tags('x.mp4', {'ItemList:Title': 'Primary', 'XMP-dc:Title': 'Alias'})
    assert mgr.get_field('Title') == 'Primary'


# -- validate ---------------------------------------------------------------

def test_validate_rejects_bad_date(mgr):
    mgr.set_field('Date Recorded', 'May 3, 1948')
    problems = mgr.validate()
    assert problems and 'Date Recorded' in problems[0]


def test_validate_int_field():
    m = MetadataManager()
    m.reload_mode('TV Episode')
    m.set_field('Season', 'abc')   # ExifTool would silently store 0xabc = 2748
    assert any('Season' in p for p in m.validate())
    m.set_field('Season', '3')
    assert m.validate() == []


def test_save_refuses_invalid_values(mgr, tmp_path):
    mgr.set_field('Date Recorded', 'garbage')
    with pytest.raises(ValueError):
        mgr.save_to_file(str(tmp_path / 'x.mp4'))


# -- write plans ------------------------------------------------------------

def test_embedded_plan_sets_aliases_and_deletes_empties(mgr):
    mgr.set_field('Title', 'Speech')
    mgr.set_field('Speakers / People', 'Truman; ; Acheson ')
    mgr.set_field('Date Recorded', '1948-05')
    plan = mgr.build_write_plan('C:/v/clip.mp4')

    assert plan.target == 'C:/v/clip.mp4' and not plan.sidecar
    sv = plan.set_values
    assert sv['ItemList:Title'] == 'Speech' and sv['XMP-dc:Title'] == 'Speech'
    assert sv['XMP-dc:Contributor'] == ['Truman', 'Acheson']
    assert sv['XMP-dc:Date'] == '1948-05'
    assert sv['ItemList:ContentCreateDate#'] == '1948'
    # hidden auto-written fields
    assert sv['ItemList:Artist'] == 'Harry S. Truman Library'
    assert sv['XMP-xmp:CreatorTool'] == f"{APP_NAME} v{APP_VERSION}"
    # empty fields are deletes, never null/"" values
    assert 'ItemList:Description' in plan.delete_tags
    assert 'XMP-iptcCore:Location' in plan.delete_tags
    assert all(v not in (None, '') for v in sv.values())
    assert not set(plan.delete_tags) & {k.rstrip('#') for k in sv}


def test_sidecar_plan_only_xmp(mgr):
    mgr.set_field('Title', 'Speech')
    mgr.set_field('Restrictions', 'None')
    plan = mgr.build_write_plan('C:/v/clip.mpg')
    assert plan.sidecar and plan.target == 'C:/v/clip.xmp'
    assert all(k.startswith('XMP-') for k in plan.set_values)
    assert all(t.startswith('XMP-') for t in plan.delete_tags)
    assert plan.set_values['XMP-dc:Title'] == 'Speech'
    assert plan.set_values['XMP-dc:Rights'] == 'None'
    assert plan.skipped == []


def test_sidecar_plan_reports_mp4_only_fields():
    m = MetadataManager()
    m.reload_mode('TV Episode')
    m.set_field('Show', 'Meet the Press')
    m.set_field('Title', 'Ep 1')
    plan = m.build_write_plan('C:/v/clip.mpeg')
    assert 'Show' in plan.skipped
    assert 'Title' not in plan.skipped


def test_set_beats_delete_for_shared_tag():
    m = MetadataManager()
    m.reload_mode('General')
    # Description has XMP alias; Comment is its own field — both ItemList, no overlap,
    # so build an explicit overlap: Comment empty must not delete a tag another field sets.
    m._field_specs = [
        {"label": "A", "tag": "ItemList:Comment", "widget": "line"},
        {"label": "B", "tag": "XMP-dc:Description", "widget": "line", "aliases": ["ItemList:Comment"]},
    ]
    m._reset_values()
    m.set_field('B', 'kept')
    plan = m.build_write_plan('x.mp4')
    assert plan.set_values['ItemList:Comment'] == 'kept'
    assert 'ItemList:Comment' not in plan.delete_tags


# -- JSON export / import --------------------------------------------------

def test_export_import_roundtrip(mgr, tmp_path):
    mgr.set_field('Title', 'Café — 1948')
    out = tmp_path / 'm.json'
    assert mgr.export_to_json(str(out))
    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['metadata']['Title'] == 'Café — 1948'

    other = MetadataManager()
    other.reload_mode('Archival Video')
    assert other.import_from_json(str(out))
    assert other.get_field('Title') == 'Café — 1948'
