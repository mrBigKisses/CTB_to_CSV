"""Read and write AutoCAD CTB binary files (PIAFILEVERSION_2.0, zlib-compressed)."""

import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path

# ── Binary envelope constants ─────────────────────────────────────────────────

_HEADER       = b"PIAFILEVERSION_2.0,CTBVER1,compress\r\n"
_CODEC_TAG    = b"pmzlibcodec"
_HEADER_LEN   = len(_HEADER)                  # 37
_CODEC_LEN    = len(_CODEC_TAG)               # 11
_UNKNOWN_OFF  = _HEADER_LEN + _CODEC_LEN      # 48  (4 unknown bytes, possibly CRC)
_UNCOMP_OFF   = _UNKNOWN_OFF + 4              # 52
_COMP_OFF     = _UNCOMP_OFF  + 4              # 56
_ZLIB_OFF     = _COMP_OFF    + 4              # 60

# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class PlotStyle:
    aci_index: int           # 0–254  (= ACI color − 1)
    localized_name: str = ""
    name: str = ""
    description: str = ""
    physical_pen_number: int = 0
    color: int = -1006632961          # 0xC3FFFFFF  — "use object color"
    mode_color: int = -1006632961
    virtual_pen_number: int = 0
    color_policy: int = 1
    screen: int = 100
    linepattern_size: float = 0.5
    linetype: int = 31                # 31 = use object linetype
    adaptive_linetype: bool = True
    lineweight: int = 0               # index into lineweight table
    fill_style: int = 73              # 73 = use object fill style
    end_style: int = 4                # 4 = use object end style
    join_style: int = 5               # 5 = use object join style


@dataclass
class CTBFile:
    apply_factor: bool = False
    description: str = ""
    aci_table_available: bool = True
    scale_factor: float = 1.0
    custom_lineweight_display_units: int = 0
    plot_styles: list[PlotStyle] = field(default_factory=list)
    # lineweight index → mm value
    lineweight_table: dict[int, float] = field(default_factory=dict)
    # preserved from original binary header (possibly CRC)
    _unknown_bytes: bytes = field(default=b"\x00\x00\x00\x00", repr=False)


# ── Color helpers ─────────────────────────────────────────────────────────────

def color_to_rgb(color_int: int) -> tuple[int, int, int]:
    """Decode a CTB signed-int color to (R, G, B)."""
    b = struct.pack(">i", color_int)   # big-endian: [flag, R, G, B]
    return b[1], b[2], b[3]


def rgb_to_color(r: int, g: int, b: int, flag: int = 0xC3) -> int:
    """Encode (R, G, B) + flag byte back to a CTB signed-int color."""
    return struct.unpack(">i", bytes([flag, r, g, b]))[0]


def color_flag(color_int: int) -> int:
    return struct.pack(">i", color_int)[0]


# ── Text-format parser ────────────────────────────────────────────────────────

def _parse_text(text: str) -> CTBFile:
    ctb = CTBFile()
    lines = text.splitlines()
    i = 0
    n = len(lines)

    def read_value(line: str) -> str:
        _, _, val = line.partition("=")
        # string values start with a quote (no closing quote in CTB format)
        return val[1:] if val.startswith('"') else val

    while i < n:
        line = lines[i].strip()

        if line.startswith("apply_factor="):
            ctb.apply_factor = read_value(line).upper() == "TRUE"
        elif line.startswith("description="):
            ctb.description = read_value(line)
        elif line.startswith("aci_table_available="):
            ctb.aci_table_available = read_value(line).upper() == "TRUE"
        elif line.startswith("scale_factor="):
            ctb.scale_factor = float(read_value(line))
        elif line.startswith("custom_lineweight_display_units="):
            ctb.custom_lineweight_display_units = int(read_value(line))
        elif line == "plot_style{":
            i += 1
            while i < n and lines[i].strip() != "}":
                block_line = lines[i].strip()
                m = re.match(r"^(\d+)\{$", block_line)
                if m:
                    idx = int(m.group(1))
                    ps = PlotStyle(aci_index=idx)
                    i += 1
                    while i < n and lines[i].strip() != "}":
                        fl = lines[i].strip()
                        if fl.startswith("localized_name="):
                            ps.localized_name = read_value(fl)
                        elif fl.startswith("name="):
                            ps.name = read_value(fl)
                        elif fl.startswith("description="):
                            ps.description = read_value(fl)
                        elif fl.startswith("physical_pen_number="):
                            ps.physical_pen_number = int(read_value(fl))
                        elif fl.startswith("color="):
                            ps.color = int(read_value(fl))
                        elif fl.startswith("mode_color="):
                            ps.mode_color = int(read_value(fl))
                        elif fl.startswith("virtual_pen_number="):
                            ps.virtual_pen_number = int(read_value(fl))
                        elif fl.startswith("color_policy="):
                            ps.color_policy = int(read_value(fl))
                        elif fl.startswith("screen="):
                            ps.screen = int(read_value(fl))
                        elif fl.startswith("linepattern_size="):
                            ps.linepattern_size = float(read_value(fl))
                        elif fl.startswith("linetype="):
                            ps.linetype = int(read_value(fl))
                        elif fl.startswith("adaptive_linetype="):
                            ps.adaptive_linetype = read_value(fl).upper() == "TRUE"
                        elif fl.startswith("lineweight="):
                            ps.lineweight = int(read_value(fl))
                        elif fl.startswith("fill_style="):
                            ps.fill_style = int(read_value(fl))
                        elif fl.startswith("end_style="):
                            ps.end_style = int(read_value(fl))
                        elif fl.startswith("join_style="):
                            ps.join_style = int(read_value(fl))
                        i += 1
                    ctb.plot_styles.append(ps)
                i += 1
        elif line == "custom_lineweight_table{":
            i += 1
            while i < n and lines[i].strip() != "}":
                tl = lines[i].strip()
                if "=" in tl:
                    k, _, v = tl.partition("=")
                    ctb.lineweight_table[int(k)] = float(v)
                i += 1

        i += 1

    ctb.plot_styles.sort(key=lambda ps: ps.aci_index)
    return ctb


# ── Text-format writer ────────────────────────────────────────────────────────

def _write_text(ctb: CTBFile) -> str:
    lines = []

    def boolstr(v: bool) -> str:
        return "TRUE" if v else "FALSE"

    lines.append(f'apply_factor={boolstr(ctb.apply_factor)}')
    lines.append(f'description="{ctb.description}')
    lines.append(f'aci_table_available={boolstr(ctb.aci_table_available)}')
    lines.append(f'scale_factor={ctb.scale_factor}')
    lines.append(f'custom_lineweight_display_units={ctb.custom_lineweight_display_units}')
    lines.append('plot_style{')

    for ps in sorted(ctb.plot_styles, key=lambda p: p.aci_index):
        lines.append(f' {ps.aci_index}{{')
        lines.append(f'  localized_name="{ps.localized_name}')
        lines.append(f'  name="{ps.name}')
        lines.append(f'  description="{ps.description}')
        lines.append(f'  physical_pen_number={ps.physical_pen_number}')
        lines.append(f'  color={ps.color}')
        lines.append(f'  mode_color={ps.mode_color}')
        lines.append(f'  virtual_pen_number={ps.virtual_pen_number}')
        lines.append(f'  color_policy={ps.color_policy}')
        lines.append(f'  screen={ps.screen}')
        lines.append(f'  linepattern_size={ps.linepattern_size}')
        lines.append(f'  linetype={ps.linetype}')
        lines.append(f'  adaptive_linetype={boolstr(ps.adaptive_linetype)}')
        lines.append(f'  lineweight={ps.lineweight}')
        lines.append(f'  fill_style={ps.fill_style}')
        lines.append(f'  end_style={ps.end_style}')
        lines.append(f'  join_style={ps.join_style}')
        lines.append(' }')

    lines.append('}')
    lines.append('custom_lineweight_table{')

    for k in sorted(ctb.lineweight_table):
        v = ctb.lineweight_table[k]
        lines.append(f' {k}={v}')

    lines.append('}')
    lines.append(' ')

    return "\n".join(lines) + "\n"


# ── Public API ────────────────────────────────────────────────────────────────

def read_ctb(path: str | Path) -> CTBFile:
    """Parse a .ctb file and return a CTBFile."""
    data = Path(path).read_bytes()

    if not data.startswith(_HEADER):
        raise ValueError(f"Not a valid CTB file (bad header): {path}")

    unknown_bytes = data[_UNKNOWN_OFF:_UNKNOWN_OFF + 4]
    compressed_size = struct.unpack_from("<I", data, _COMP_OFF)[0]
    zlib_data = data[_ZLIB_OFF: _ZLIB_OFF + compressed_size]
    text = zlib.decompress(zlib_data).decode("ascii")

    ctb = _parse_text(text)
    ctb._unknown_bytes = unknown_bytes
    return ctb


def write_ctb(ctb: CTBFile, path: str | Path) -> None:
    """Serialise a CTBFile back to a .ctb binary file."""
    text = _write_text(ctb)
    uncompressed = text.encode("ascii")
    compressed = zlib.compress(uncompressed, level=9)

    # Rebuild binary envelope
    out = bytearray()
    out += _HEADER
    out += _CODEC_TAG
    out += ctb._unknown_bytes                            # 4 unknown bytes (preserved)
    out += struct.pack("<I", len(uncompressed))          # uncompressed size
    out += struct.pack("<I", len(compressed))            # compressed size
    out += compressed

    Path(path).write_bytes(bytes(out))
