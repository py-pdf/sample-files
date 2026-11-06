"""
Create a PDF whose picture follows the clock of the viewer, using JavaScript.

The page shows a landscape. A document-level JavaScript (ISO 32000-2:2020,
7.7.4 and 12.6.4.17) runs once per second and shows

* the sky of the current hour: the sun or the moon on its arc, the brightness
  of the sky and of the ground, and stars at night;
* the tree of the current month: bare with snow in winter, buds in March,
  blossoms in April, green leaves in summer, colored and falling leaves in
  autumn;
* a penguin that walks across the page once per hour: to the right in the
  first half hour, to the left in the second one, one position per minute,
  with the feet and flippers changing every second;
* the time as a digital clock and the name of the month, in text fields.

Every picture is the appearance stream of a read-only push button
(ISO 32000-2:2020, 12.7.5.2), and all but one picture of each group are hidden
(annotation flag Hidden, 12.5.3). The script switches them with the display
property of the fields of the Acrobat JavaScript API. PDF.js only applies it to
a push button that has a JavaScript action, so every picture has one that does
nothing. A viewer without JavaScript shows the default pictures: noon in June,
the penguin in the middle, and "--:--:--" with "needs JavaScript" in the text
fields.

The file is written without any PDF library, so that every object is under
control. The text fields use the standard font Courier-Bold, which is not
embedded.

Usage: python create_javascript_clock.py
"""

from __future__ import annotations

import hashlib
import math
import random
import zlib
from dataclasses import dataclass
from typing import Union

OUTPUT = "javascript-clock.pdf"

PAGE_WIDTH = 800
PAGE_HEIGHT = 500
HORIZON = 160

# The pictures shown by a viewer without JavaScript
DEFAULT_HOUR = 12
DEFAULT_MONTH = 6
DEFAULT_MINUTE = 15

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# Field flags (ISO 32000-2:2020, 12.7.4.1 and 12.7.5.2.1)
READ_ONLY = 1
PUSH_BUTTON = 1 << 16
# Annotation flags (ISO 32000-2:2020, 12.5.3)
HIDDEN = 2
PRINT = 4

JAVASCRIPT = """
var MONTHS = [%(months)s];
var doc = this;
var shown = {hour: "%(hour)s", month: "%(month)s", penguin: "%(penguin)s"};

function pad(number) {
    return (number < 10 ? "0" : "") + number;
}

function show(group, name) {
    if (shown[group] == name) {
        return;
    }
    doc.getField(name).display = display.visible;
    doc.getField(shown[group]).display = display.hidden;
    shown[group] = name;
}

function tick() {
    var now = new Date();
    var hour = now.getHours();
    var minute = now.getMinutes();
    var second = now.getSeconds();
    show("hour", "hour." + pad(hour));
    show("month", "month." + pad(now.getMonth() + 1));
    show("penguin", "penguin." + pad(minute) + (second %% 2 ? ".b" : ".a"));
    doc.getField("clock").value = pad(hour) + ":" + pad(minute) + ":" + pad(second);
    doc.getField("month").value = MONTHS[now.getMonth()];
}

tick();
// Acrobat stops the timer when nothing refers to it any more.
var timer = app.setInterval("tick()", 1000);
"""


@dataclass(frozen=True)
class Name:
    value: str


@dataclass(frozen=True)
class Ref:
    number: int


@dataclass
class Stream:
    dictionary: dict[str, PdfValue]
    data: bytes


PdfValue = Union[None, bool, int, float, str, bytes, Name, Ref, list, dict, Stream]


def serialize(value: PdfValue) -> bytes:
    if value is None:
        return b"null"
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, (int, float)):
        return str(round(value, 3)).encode()
    if isinstance(value, Name):
        return b"/" + value.value.encode()
    if isinstance(value, Ref):
        return f"{value.number} 0 R".encode()
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return b"(" + escaped.encode("latin-1") + b")"
    if isinstance(value, bytes):
        return b"<" + value.hex().upper().encode() + b">"
    if isinstance(value, list):
        return b"[" + b" ".join(serialize(item) for item in value) + b"]"
    if isinstance(value, dict):
        entries = b" ".join(b"/" + key.encode() + b" " + serialize(item) for key, item in value.items())
        return b"<< " + entries + b" >>"
    raise TypeError(f"Cannot serialize {value!r}")


class Document:
    def __init__(self) -> None:
        self.objects: dict[int, PdfValue] = {}

    def add(self, value: PdfValue) -> Ref:
        ref = Ref(len(self.objects) + 1)
        self.objects[ref.number] = value
        return ref

    def write(self, path: str, root: Ref) -> None:
        body = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, value in self.objects.items():
            offsets.append(len(body))
            body += f"{number} 0 obj\n".encode()
            if isinstance(value, Stream):
                dictionary = {**value.dictionary, "Length": len(value.data)}
                body += serialize(dictionary) + b"\nstream\n" + value.data + b"\nendstream"
            else:
                body += serialize(value)
            body += b"\nendobj\n"
        file_id = hashlib.md5(bytes(body)).digest()
        xref_offset = len(body)
        body += f"xref\n0 {len(self.objects) + 1}\n".encode()
        body += b"0000000000 65535 f\r\n"
        for offset in offsets:
            body += f"{offset:010d} 00000 n\r\n".encode()
        trailer = {"Size": len(self.objects) + 1, "Root": root, "ID": [file_id, file_id]}
        body += b"trailer\n" + serialize(trailer) + f"\nstartxref\n{xref_offset}\n%%EOF\n".encode()
        with open(path, "wb") as file:
            file.write(body)


def compressed(dictionary: dict[str, PdfValue], operators: str) -> Stream:
    return Stream({**dictionary, "Filter": Name("FlateDecode")}, zlib.compress(operators.encode("latin-1"), 9))


# --- Drawing ---------------------------------------------------------------

Color = tuple[float, float, float]

# The control point distance of a Bézier curve approximating a quarter circle
KAPPA = 0.5523


def fill_color(color: Color) -> str:
    return "%.3f %.3f %.3f rg\n" % color


def stroke_color(color: Color) -> str:
    return "%.3f %.3f %.3f RG\n" % color


def ellipse(x: float, y: float, rx: float, ry: float) -> str:
    """Return the path of an ellipse, made of four Bézier curves."""
    kx, ky = rx * KAPPA, ry * KAPPA
    return (
        f"{x + rx:.2f} {y:.2f} m\n"
        f"{x + rx:.2f} {y + ky:.2f} {x + kx:.2f} {y + ry:.2f} {x:.2f} {y + ry:.2f} c\n"
        f"{x - kx:.2f} {y + ry:.2f} {x - rx:.2f} {y + ky:.2f} {x - rx:.2f} {y:.2f} c\n"
        f"{x - rx:.2f} {y - ky:.2f} {x - kx:.2f} {y - ry:.2f} {x:.2f} {y - ry:.2f} c\n"
        f"{x + kx:.2f} {y - ry:.2f} {x + rx:.2f} {y - ky:.2f} {x + rx:.2f} {y:.2f} c\n"
    )


def fill_ellipse(color: Color, x: float, y: float, rx: float, ry: float | None = None) -> str:
    return fill_color(color) + ellipse(x, y, rx, rx if ry is None else ry) + "f\n"


def mix(a: Color, b: Color, t: float) -> Color:
    t = min(max(t, 0.0), 1.0)
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def scale(color: Color, factor: float) -> Color:
    return (color[0] * factor, color[1] * factor, color[2] * factor)


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    t = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# --- The sky of an hour ----------------------------------------------------

NIGHT_TOP, NIGHT_HORIZON = (0.02, 0.03, 0.10), (0.08, 0.10, 0.25)
DAY_TOP, DAY_HORIZON = (0.25, 0.55, 0.95), (0.70, 0.87, 1.00)
TWILIGHT_TOP, TWILIGHT_HORIZON = (0.35, 0.30, 0.55), (1.00, 0.55, 0.30)
GRASS, HILL = (0.35, 0.65, 0.25), (0.28, 0.55, 0.22)

def sun_or_moon_position(angle: float) -> tuple[float, float]:
    """Return the position on the arc from the left (angle 0) to the right (angle pi).

    The arc starts a bit above the horizon, so that the sun rises and sets half
    hidden behind the hills.
    """
    return 400 - 330 * math.cos(angle), HORIZON + 45 + 250 * math.sin(angle)


def draw_hour(hour: int) -> str:
    # The elevation of the sun: -1 at midnight, 0 at 6 and 18 o'clock, 1 at noon
    elevation = math.sin(math.pi * (hour - 6) / 12)
    daylight = smoothstep(-0.3, 0.4, elevation)
    twilight = math.exp(-((elevation / 0.25) ** 2))
    top = mix(mix(NIGHT_TOP, DAY_TOP, daylight), TWILIGHT_TOP, twilight * 0.5)
    horizon = mix(mix(NIGHT_HORIZON, DAY_HORIZON, daylight), TWILIGHT_HORIZON, twilight * 0.8)

    operators = ""
    bands = 40
    band_height = (PAGE_HEIGHT - HORIZON) / bands
    for band in range(bands):
        color = mix(horizon, top, (band / (bands - 1)) ** 0.8)
        # Every band reaches the top, so that no gap shows between the bands.
        bottom = HORIZON + band * band_height
        operators += fill_color(color) + f"0 {bottom:.2f} {PAGE_WIDTH} {PAGE_HEIGHT - bottom:.2f} re f\n"

    if elevation < -0.2:
        rng = random.Random(7)
        for _ in range(70):
            x, y = rng.uniform(5, PAGE_WIDTH - 5), rng.uniform(HORIZON + 40, PAGE_HEIGHT - 5)
            brightness = rng.uniform(0.5, 1.0) * min(1.0, (-elevation - 0.2) * 2)
            operators += fill_ellipse(mix(top, (1.0, 1.0, 0.9), brightness), x, y, rng.uniform(0.8, 1.8))

    if 6 <= hour <= 18:
        x, y = sun_or_moon_position(math.pi * (hour - 6) / 12)
        sun = mix((1.0, 0.45, 0.15), (1.0, 0.88, 0.25), smoothstep(0.0, 0.5, elevation))
        operators += "q /Glow gs\n" + fill_ellipse(sun, x, y, 46) + fill_ellipse(sun, x, y, 36) + "Q\n"
        operators += fill_ellipse(sun, x, y, 28)
    if hour >= 18 or hour <= 6:
        x, y = sun_or_moon_position(math.pi * ((hour - 18) % 24) / 12)
        operators += "q /Glow gs\n" + fill_ellipse((0.9, 0.9, 0.8), x, y, 32) + "Q\n"
        operators += fill_ellipse((0.95, 0.94, 0.82), x, y, 22)
        for dx, dy, r in ((-7, 6, 4.5), (6, -5, 6), (8, 9, 2.5), (-5, -10, 3)):
            operators += fill_ellipse((0.82, 0.81, 0.72), x + dx, y + dy, r)

    light = 0.25 + 0.75 * daylight
    operators += fill_ellipse(scale(HILL, light), 170, HORIZON - 10, 260, 60)
    operators += fill_ellipse(scale(HILL, light * 0.9), 650, HORIZON - 20, 300, 70)
    operators += fill_color(scale(GRASS, light)) + f"0 0 {PAGE_WIDTH} {HORIZON} re f\n"
    return operators


# --- The tree of a month ---------------------------------------------------

TREE_BASE = (600, 140)
CROWN = (600, 330, 125, 100)  # center and radii of the crown
# The tree is drawn at TREE_BASE and placed smaller in the middle of the page,
# below the arc of the sun and the moon, so that it hides them at no hour.
TREE_PLACEMENT = "0.88 0 0 0.75 -128 35 cm\n"
TREE_RECT = [259, 95, 541, 373]
BARK = (0.40, 0.26, 0.13)
SNOW = (0.96, 0.97, 1.00)

TRUNK = (
    fill_color(BARK)
    + "585 140 m 615 140 l 607 300 l 593 300 l f\n"
    + stroke_color(BARK)
    + "1 J\n"
    + "11 w 600 235 m 525 315 l S 10 w 601 255 m 685 330 l S\n"
    + "8 w 600 285 m 555 385 l S 8 w 601 290 m 645 395 l S\n"
    + "7 w 600 295 m 600 410 l S 5 w 545 300 m 505 340 l S 5 w 660 315 m 705 350 l S\n"
)
SNOW_ON_BRANCHES = "".join(
    fill_ellipse(SNOW, x, y, rx, 3.5)
    for x, y, rx in ((560, 282, 18), (530, 322, 10), (645, 297, 20), (685, 335, 9), (575, 345, 12), (625, 352, 12), (600, 413, 7))
)

# Fraction of the leaves on the tree, their colors, and the number of leaves on the ground
SEASONS: dict[int, tuple[float, list[Color], int]] = {
    1: (0.0, [], 0),
    2: (0.0, [], 0),
    3: (0.25, [(0.65, 0.85, 0.35)], 0),
    4: (0.6, [(1.00, 0.75, 0.85), (1.00, 0.92, 0.95), (0.60, 0.85, 0.35)], 0),
    5: (0.9, [(0.45, 0.80, 0.30), (0.55, 0.85, 0.35)], 0),
    6: (1.0, [(0.30, 0.68, 0.22), (0.38, 0.75, 0.28)], 0),
    7: (1.0, [(0.22, 0.58, 0.18), (0.30, 0.65, 0.22)], 0),
    8: (1.0, [(0.18, 0.50, 0.15), (0.25, 0.55, 0.18), (0.75, 0.70, 0.20)], 0),
    9: (1.0, [(0.30, 0.55, 0.15), (0.70, 0.70, 0.15), (0.85, 0.65, 0.10)], 5),
    10: (0.8, [(0.90, 0.45, 0.10), (0.80, 0.20, 0.10), (0.95, 0.75, 0.15)], 25),
    11: (0.25, [(0.55, 0.35, 0.15), (0.70, 0.45, 0.15)], 45),
    12: (0.0, [], 0),
}


def draw_month(month: int) -> str:
    fraction, colors, fallen = SEASONS[month]
    operators = TREE_PLACEMENT
    if month in (12, 1, 2):
        operators += fill_ellipse(SNOW, TREE_BASE[0], TREE_BASE[1] - 5, 130, 22)
    rng = random.Random(month)
    for _ in range(fallen):
        x, y = rng.uniform(480, 720), rng.uniform(105, 150)
        operators += fill_ellipse(rng.choice(colors), x, y, 6, 3)
    operators += "q\n" + TRUNK + "Q\n"
    if month in (12, 1, 2):
        operators += SNOW_ON_BRANCHES
    # The same positions in every month, so that the leaves grow and fall
    rng = random.Random(0)
    cx, cy, rx, ry = CROWN
    for _ in range(260):
        angle, distance = rng.uniform(0, 2 * math.pi), math.sqrt(rng.random())
        x, y = cx + rx * distance * math.cos(angle), cy + ry * distance * math.sin(angle)
        radius = rng.uniform(9, 14)
        pick, choice = rng.random(), rng.random()
        if pick < fraction:
            size = radius * (0.45 if month == 3 else 0.8 if month == 4 else 1.0)
            operators += fill_ellipse(colors[int(choice * len(colors))], x, y, size)
    return operators


# --- The penguin -----------------------------------------------------------

BLACK, WHITE, ORANGE = (0.08, 0.08, 0.12), (0.97, 0.97, 0.97), (1.0, 0.55, 0.05)
PENGUIN_Y = 35


def draw_penguin(step: bool) -> str:
    """Return the penguin facing right, standing at (0, 0); step changes the pose."""
    tilt = math.radians(-6 if step else 6)
    front, back = (14, 6) if step else (-10, 4)
    operators = fill_ellipse(ORANGE, front, 3, 11, 4) + fill_ellipse(ORANGE, back, 5 if step else 3, 10, 4)
    cos, sin = math.cos(tilt), math.sin(tilt)
    operators += f"q {cos:.4f} {sin:.4f} {-sin:.4f} {cos:.4f} 0 4 cm\n"
    operators += fill_ellipse(BLACK, 0, 40, 24, 38) + fill_ellipse(WHITE, 5, 36, 16, 30)
    flipper = math.radians(35 if step else -20)
    c, s = math.cos(flipper), math.sin(flipper)
    operators += f"q {c:.4f} {s:.4f} {-s:.4f} {c:.4f} -16 52 cm\n" + fill_ellipse(BLACK, 0, -14, 7, 18) + "Q\n"
    operators += fill_ellipse(BLACK, 4, 78, 17) + fill_ellipse(WHITE, 10, 79, 9, 8)
    operators += fill_ellipse(BLACK, 12, 81, 2.6)
    operators += fill_color(ORANGE) + "18 79 m 31 74 l 18 70 l f\n"
    return operators + "Q\n"


def penguin_x(minute: int) -> tuple[float, bool]:
    """Return where the penguin is in the minute, and whether it walks to the right."""
    if minute < 30:
        return 70 + 660 * minute / 29, True
    return 730 - 660 * (minute - 30) / 29, False


# --- The document ----------------------------------------------------------


def main() -> None:
    doc = Document()
    glow = {"Type": Name("ExtGState"), "ca": 0.3}
    courier = doc.add({"Type": Name("Font"), "Subtype": Name("Type1"), "BaseFont": Name("Courier-Bold"), "Encoding": Name("WinAnsiEncoding")})
    helvetica = doc.add({"Type": Name("Font"), "Subtype": Name("Type1"), "BaseFont": Name("Helvetica"), "Encoding": Name("WinAnsiEncoding")})

    fields: list[Ref] = []
    # PDF.js only lets the script show and hide a push button that has a
    # JavaScript action; the action does nothing.
    no_action = doc.add({"Type": Name("Action"), "S": Name("JavaScript"), "JS": "// Nothing happens on a click."})

    def picture(name: str, rect: list[float], operators: str, visible: bool, resources: dict | None = None) -> None:
        # The bounding box is the rectangle, so the appearance is drawn in page coordinates.
        appearance = doc.add(
            compressed({"Type": Name("XObject"), "Subtype": Name("Form"), "BBox": rect, "Resources": resources or {}}, operators)
        )
        fields.append(
            doc.add(
                {
                    "Type": Name("Annot"),
                    "Subtype": Name("Widget"),
                    "FT": Name("Btn"),
                    "Ff": PUSH_BUTTON | READ_ONLY,
                    "T": name,
                    "Rect": rect,
                    "F": PRINT if visible else PRINT | HIDDEN,
                    "MK": {},
                    "A": no_action,
                    "AP": {"N": appearance},
                }
            )
        )

    for hour in range(24):
        picture(f"hour.{hour:02d}", [0, 0, PAGE_WIDTH, PAGE_HEIGHT], draw_hour(hour), hour == DEFAULT_HOUR, {"ExtGState": {"Glow": glow}})
    for month in range(1, 13):
        picture(f"month.{month:02d}", TREE_RECT, draw_month(month), month == DEFAULT_MONTH)

    # The four penguins are drawn once and placed by every picture of a minute.
    penguins = {}
    for right in (True, False):
        for step in (False, True):
            mirror = "" if right else "-1 0 0 1 0 0 cm\n"
            penguins[right, step] = doc.add(
                compressed({"Type": Name("XObject"), "Subtype": Name("Form"), "BBox": [-45, -5, 45, 100]}, mirror + draw_penguin(step))
            )
    for minute in range(60):
        x, right = penguin_x(minute)
        for step, pose in ((False, "a"), (True, "b")):
            operators = f"q 1 0 0 1 {x:.2f} {PENGUIN_Y} cm /Penguin Do Q\n"
            visible = minute == DEFAULT_MINUTE and pose == "a"
            resources = {"XObject": {"Penguin": penguins[right, step]}}
            picture(f"penguin.{minute:02d}.{pose}", [x - 45, PENGUIN_Y - 5, x + 45, PENGUIN_Y + 100], operators, visible, resources)

    def text_field(name: str, rect: list[float], size: float, color: Color, value: str) -> None:
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        # Every glyph of Courier-Bold is 600 units wide.
        x = (width - len(value) * 0.6 * size) / 2
        y = (height - size * 0.6) / 2
        operators = (
            "0 0 0 rg 0 0 %.2f %.2f re f\n/Tx BMC q BT /Cour %s Tf %s%.2f %.2f Td (%s) Tj ET Q EMC\n"
            % (width, height, size, fill_color(color), x, y, value)
        )
        appearance = doc.add(
            compressed(
                {"Type": Name("XObject"), "Subtype": Name("Form"), "BBox": [0, 0, width, height], "Resources": {"Font": {"Cour": courier}}},
                operators,
            )
        )
        fields.append(
            doc.add(
                {
                    "Type": Name("Annot"),
                    "Subtype": Name("Widget"),
                    "FT": Name("Tx"),
                    "Ff": READ_ONLY,
                    "T": name,
                    "V": value,
                    "DA": f"/Cour {size} Tf " + fill_color(color).strip(),
                    "Q": 1,
                    "Rect": rect,
                    "F": PRINT,
                    "MK": {"BG": [0, 0, 0]},
                    "AP": {"N": appearance},
                }
            )
        )

    # In the corner left of the sun at 10 o'clock and the moon at 22 o'clock
    text_field("clock", [10, 446, 190, 490], 30, (0.2, 1.0, 0.3), "--:--:--")
    text_field("month", [10, 424, 190, 444], 13, WHITE, "needs JavaScript")

    javascript = JAVASCRIPT % {
        "months": ", ".join(f'"{month}"' for month in MONTHS),
        "hour": f"hour.{DEFAULT_HOUR:02d}",
        "month": f"month.{DEFAULT_MONTH:02d}",
        "penguin": f"penguin.{DEFAULT_MINUTE:02d}.a",
    }
    script = doc.add(compressed({}, javascript.lstrip()))
    action = doc.add({"Type": Name("Action"), "S": Name("JavaScript"), "JS": script})

    # The page shows the default sky as well, for programs that do not show annotations.
    page_content = doc.add(compressed({}, draw_hour(DEFAULT_HOUR)))
    pages = Ref(len(doc.objects) + 2)
    page = doc.add(
        {
            "Type": Name("Page"),
            "Parent": pages,
            "MediaBox": [0, 0, PAGE_WIDTH, PAGE_HEIGHT],
            "Resources": {"ExtGState": {"Glow": glow}},
            "Contents": page_content,
            "Annots": fields,
        }
    )
    assert doc.add({"Type": Name("Pages"), "Kids": [page], "Count": 1}) == pages
    root = doc.add(
        {
            "Type": Name("Catalog"),
            "Pages": pages,
            "AcroForm": {
                "Fields": fields,
                "DA": "/Helv 0 Tf 0 g",
                "DR": {"Font": {"Cour": courier, "Helv": helvetica}},
            },
            "Names": {"JavaScript": {"Names": ["Clock", action]}},
        }
    )
    for field in fields:
        doc.objects[field.number]["P"] = page
    doc.write(OUTPUT, root)


if __name__ == "__main__":
    main()
