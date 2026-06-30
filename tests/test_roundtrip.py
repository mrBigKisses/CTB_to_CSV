"""Round-trip and validation tests."""

import re
import zlib
from pathlib import Path

import pytest

from ctb_csv.ctb_parser import read_ctb, write_ctb, color_to_rgb, rgb_to_color
from ctb_csv.csv_handler import ctb_to_csv, csv_to_ctb
from ctb_csv.validator import validate_csv

SAMPLE = Path(__file__).parent.parent / "samples" / "S10 Generico.ctb"


@pytest.fixture(scope="module")
def ctb():
    return read_ctb(SAMPLE)


def test_read_plot_style_count(ctb):
    assert len(ctb.plot_styles) == 255


def test_aci_index_range(ctb):
    indices = {ps.aci_index for ps in ctb.plot_styles}
    assert indices == set(range(255))


def test_lineweight_table(ctb):
    assert len(ctb.lineweight_table) == 27
    assert ctb.lineweight_table[7] == pytest.approx(0.2)
    assert ctb.lineweight_table[25] == pytest.approx(2.0)


def test_color_decode_encode():
    raw = -1023410176     # black, flag=0xC3
    r, g, b = color_to_rgb(raw)
    assert (r, g, b) == (0, 0, 0)
    assert rgb_to_color(r, g, b, 0xC3) == raw

    raw2 = -1006632961    # white/object-color, flag=0xC3
    r, g, b = color_to_rgb(raw2)
    assert (r, g, b) == (255, 255, 255)
    assert rgb_to_color(r, g, b, 0xC3) == raw2


def test_csv_export_and_validate(ctb, tmp_path):
    csv_path = tmp_path / "test.csv"
    ctb_to_csv(ctb, csv_path)
    assert csv_path.exists()
    issues = validate_csv(csv_path)
    assert issues == [], f"Unexpected validation issues: {issues}"


def test_round_trip_content(ctb, tmp_path):
    """CSV → CTB round-trip must produce functionally identical content."""
    csv_path = tmp_path / "test.csv"
    ctb_to_csv(ctb, csv_path)
    ctb2 = csv_to_ctb(csv_path, ctb)
    out_ctb = tmp_path / "test_rt.ctb"
    write_ctb(ctb2, out_ctb)

    orig_text = zlib.decompress(SAMPLE.read_bytes()[60:]).decode("ascii")
    rt_text   = zlib.decompress(out_ctb.read_bytes()[60:]).decode("ascii")

    def parse_entries(text):
        entries = {}
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if re.match(r"^\d+\{$", stripped):
                idx = int(stripped[:-1])
                fields = {}
                i += 1
                while i < len(lines) and lines[i].strip() != "}":
                    fl = lines[i].strip()
                    if "=" in fl:
                        k, _, v = fl.partition("=")
                        fields[k.strip()] = v.strip().lstrip('"')
                    i += 1
                entries[idx] = fields
            i += 1
        return entries

    orig_entries = parse_entries(orig_text)
    rt_entries   = parse_entries(rt_text)

    assert len(rt_entries) == 255
    for idx in range(255):
        assert orig_entries[idx] == rt_entries[idx], f"Mismatch at index {idx}"
