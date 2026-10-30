"""
Create a PDF file showing the same image twice, once with and once without PNG predictors.

Both images are compressed with /FlateDecode. The left one, the reference, is
stored without a predictor. The right one uses /Predictor 15 (ISO 32000-2:2020,
7.4.4.4): each row of the image starts with a byte selecting the PNG filter
of the row. The image is divided into five bands of 50 rows, one for each of
the PNG filters None, Sub, Up, Average and Paeth.

If a PDF processor decodes both images correctly, they look the same, and
their decoded data is identical. An error in one of the filters shows up as
stripes or smears starting in the band of the filter: the Sub and Paeth
filters pass errors on to the right, and the Up, Average and Paeth filters
down to the following rows.

The image is an RGB image with 8 bits per component:

* red increases from left to right;
* green decreases by about one per row, from top to bottom, so that the Up
  filter adds a byte above of up to 255 to a filtered byte of 255;
* blue forms sharp-edged concentric rings, so that bytes change between 0
  and 255 from one pixel to the next, both horizontally and vertically.

The file is written without any PDF library, so that every object is under
control. The font is the standard font Helvetica, which is not embedded.

Usage: python create_png_predictors_pdf.py
"""

from __future__ import annotations

import hashlib
import zlib

OUTPUT = "png-predictors.pdf"

WIDTH = 256
HEIGHT = 250
BYTES_PER_PIXEL = 3
FILTERS = ["None", "Sub", "Up", "Average", "Paeth"]
BAND_HEIGHT = HEIGHT // len(FILTERS)

PAGE_WIDTH = 680
PAGE_HEIGHT = 420
IMAGE_BOTTOM = 70
REFERENCE_LEFT = 40
PREDICTED_LEFT = 336


def pixel(x: int, y: int) -> tuple[int, int, int]:
    red = x
    green = 255 - y * 255 // (HEIGHT - 1)
    distance_squared = (x - WIDTH // 2) ** 2 + (y - HEIGHT // 2) ** 2
    blue = 255 if int(distance_squared**0.5) // 12 % 2 == 0 else 0
    return red, green, blue


def image_rows() -> list[bytes]:
    return [
        bytes(value for x in range(WIDTH) for value in pixel(x, y))
        for y in range(HEIGHT)
    ]


def paeth_predictor(left: int, up: int, up_left: int) -> int:
    p = left + up - up_left
    dist_left = abs(p - left)
    dist_up = abs(p - up)
    dist_up_left = abs(p - up_left)
    if dist_left <= dist_up and dist_left <= dist_up_left:
        return left
    if dist_up <= dist_up_left:
        return up
    return up_left


def filter_row(filter_type: int, row: bytes, previous: bytes) -> bytes:
    """Apply a PNG filter to a row, as described in section 9 of the PNG specification."""
    filtered = bytearray([filter_type])
    for i, value in enumerate(row):
        left = row[i - BYTES_PER_PIXEL] if i >= BYTES_PER_PIXEL else 0
        up = previous[i]
        up_left = previous[i - BYTES_PER_PIXEL] if i >= BYTES_PER_PIXEL else 0
        prediction = [
            0,
            left,
            up,
            (left + up) // 2,
            paeth_predictor(left, up, up_left),
        ][filter_type]
        filtered.append((value - prediction) % 256)
    return bytes(filtered)


def predicted_data(rows: list[bytes]) -> bytes:
    data = bytearray()
    previous = bytes(len(rows[0]))
    for y, row in enumerate(rows):
        data += filter_row(y // BAND_HEIGHT, row, previous)
        previous = row
    return bytes(data)


def escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def show_text(text: str, x: float, y: float, size: float) -> str:
    return f"BT /F1 {size} Tf {x} {y} Td ({escape(text)}) Tj ET\n"


def content_stream() -> bytes:
    image_top = IMAGE_BOTTOM + HEIGHT
    operators = [
        show_text("PNG predictors", REFERENCE_LEFT, 385, 18),
        show_text(
            "Both images must look the same. The left one has no predictor, the right one uses /Predictor 15,",
            REFERENCE_LEFT,
            362,
            10,
        ),
        show_text(
            "with a different PNG filter for each band of 50 rows. A decoding error shows as stripes or smears.",
            REFERENCE_LEFT,
            348,
            10,
        ),
        show_text("Reference: no predictor", REFERENCE_LEFT, image_top + 6, 9),
        show_text("PNG predictors", PREDICTED_LEFT, image_top + 6, 9),
        f"q {WIDTH} 0 0 {HEIGHT} {REFERENCE_LEFT} {IMAGE_BOTTOM} cm /Reference Do Q\n",
        f"q {WIDTH} 0 0 {HEIGHT} {PREDICTED_LEFT} {IMAGE_BOTTOM} cm /Predicted Do Q\n",
        "0.5 w\n",
    ]
    label_left = PREDICTED_LEFT + WIDTH + 10
    for band, name in enumerate(FILTERS):
        band_top = image_top - band * BAND_HEIGHT
        if band > 0:
            operators.append(
                f"{label_left - 8} {band_top} m {label_left + 50} {band_top} l S\n"
            )
        operators.append(
            show_text(
                f"{band + 1}: {name}", label_left, band_top - BAND_HEIGHT / 2 - 3, 9
            )
        )
    operators.append(
        show_text(
            f"Image: {WIDTH} x {HEIGHT} pixels, RGB, 8 bits per component",
            REFERENCE_LEFT,
            40,
            9,
        )
    )
    return "".join(operators).encode("latin-1")


def stream(dictionary: str, data: bytes) -> bytes:
    return (
        f"<< {dictionary} /Length {len(data)} >>\nstream\n".encode()
        + data
        + b"\nendstream"
    )


def main() -> None:
    rows = image_rows()
    image_dictionary = (
        f"/Type /XObject /Subtype /Image /Width {WIDTH} /Height {HEIGHT} "
        "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 4 0 R >> /XObject << /Reference 6 0 R /Predicted 7 0 R >> >> "
            "/Contents 5 0 R >>"
        ).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        stream("/Filter /FlateDecode", zlib.compress(content_stream(), 9)),
        stream(image_dictionary, zlib.compress(b"".join(rows), 9)),
        stream(
            f"{image_dictionary} /DecodeParms << /Predictor 15 /Colors 3 /BitsPerComponent 8 /Columns {WIDTH} >>",
            zlib.compress(predicted_data(rows), 9),
        ),
    ]

    body = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        body += f"{offset:010d} 00000 n \n".encode()
    file_id = hashlib.md5(bytes(body)).hexdigest().upper()  # noqa: S324
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /ID [<{file_id}> <{file_id}>] >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    with open(OUTPUT, "wb") as f:
        f.write(body)


if __name__ == "__main__":
    main()
