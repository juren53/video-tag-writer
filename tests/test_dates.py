"""Date parsing/conversion — the ©day rules come from the 2026-11-11 ExifTool probe."""

import re

import pytest

from video_tag_writer.metadata import parse_iso_date, display_date, date_tag_value


@pytest.mark.parametrize("value,expected", [
    ("1948", (1948, None, None)),
    ("1948-05", (1948, 5, None)),
    ("1948-05-03", (1948, 5, 3)),
    ("1948-5-3", (1948, 5, 3)),
])
def test_parse_iso_date_valid(value, expected):
    assert parse_iso_date(value) == expected


@pytest.mark.parametrize("value", ["", "48", "1948/05/03", "May 3, 1948", "1948-13", "1948-02-30", "1948-05-03T10:00"])
def test_parse_iso_date_invalid(value):
    with pytest.raises(ValueError):
        parse_iso_date(value)


@pytest.mark.parametrize("raw,expected", [
    ("1948:05:03 00:00:00-06:00", "1948-05-03"),
    ("1948:05:03 00:00:00Z", "1948-05-03"),
    ("1948-05-03T00:00:00Z", "1948-05-03"),
    ("1948:05", "1948-05"),
    ("1948", "1948"),
    (1948, "1948"),
    ("circa 1948", "circa 1948"),
    ("", ""),
])
def test_display_date(raw, expected):
    assert display_date(raw) == expected


def test_xmp_dates_keep_precision():
    assert date_tag_value("XMP-dc:Date", "1948") == ("XMP-dc:Date", "1948")
    assert date_tag_value("XMP-dc:Date", "1948-5") == ("XMP-dc:Date", "1948-05")
    assert date_tag_value("XMP-dc:Date", "1948-05-03") == ("XMP-dc:Date", "1948-05-03")


def test_itemlist_year_and_month_written_as_raw_year():
    # ExifTool rejects partial dates for ©day except a raw ('#') year
    assert date_tag_value("ItemList:ContentCreateDate", "1948") == ("ItemList:ContentCreateDate#", "1948")
    assert date_tag_value("ItemList:ContentCreateDate", "1948-05") == ("ItemList:ContentCreateDate#", "1948")


def test_itemlist_full_date_is_local_midnight_with_offset():
    key, val = date_tag_value("ItemList:ContentCreateDate", "1948-05-03")
    assert key == "ItemList:ContentCreateDate"
    assert re.fullmatch(r"1948:05:03 00:00:00([+-]\d{2}:\d{2}|Z)", val)
    # Round-trips to the same calendar date for display
    assert display_date(val) == "1948-05-03"
