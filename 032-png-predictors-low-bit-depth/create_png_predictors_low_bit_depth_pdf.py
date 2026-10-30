"""
Create a PDF file showing PNG predictors for images with 1, 2 and 4 bits per component.

Each page shows the same grayscale image twice, once with and once without PNG
predictors, like 031-png-predictors does for an RGB image with 8 bits per
component. Both images are compressed with /FlateDecode. The left one, the
reference, is stored without a predictor. The right one uses /Predictor 15
(ISO 32000-2:2020, 7.4.4.4): each row of the image starts with a byte selecting
the PNG filter of the row. The image is divided into five bands of 50 rows, one
for each of the PNG filters None, Sub, Up, Average and Paeth.

The PNG filters work on bytes, not on pixels. The Sub, Average and Paeth
filters predict a byte from the byte one complete pixel to its left. If a pixel
is smaller than a byte, they use the byte directly to its left: the number of
bytes per complete pixel is rounded up to one (section 9.2 of the PNG
specification). A decoder that rounds it down to zero instead uses the byte
itself, and decodes the bands of these filters wrongly.

If a PDF processor decodes both images correctly, they look the same, and
their decoded data is identical. An error in one of the filters shows up as
stripes or smears starting in the band of the filter.

The image has the same pattern on each page: concentric rings, whose shade
increases from left to right, and is inverted between neighboring rings.

The file is written without any PDF library, so that every object is under
control. The font is the standard font Helvetica, which is not embedded.

Usage: python create_png_predictors_low_bit_depth_pdf.py
"""

from __future__ import annotations

import hashlib
import zlib

OUTPUT = "png-predictors-low-bit-depth.pdf"

WIDTH = 256
HEIGHT = 250
BITS_PER_COMPONENT = [1, 2, 4]
BYTES_PER_PIXEL = 1  # Bytes per complete pixel, rounded up to one
FILTERS = ["None", "Sub", "Up", "Average", "Paeth"]
BAND_HEIGHT = HEIGHT // len(FILTERS)

PAGE_WIDTH = 680
PAGE_HEIGHT = 420
IMAGE_BOTTOM = 70
REFERENCE_LEFT = 40
PREDICTED_LEFT = 336


def pixel(x: int, y: int, bits: int) -> int:
    """Return the gray level of a pixel, between 0 and 2**bits - 1."""
    maximum = (1 << bits) - 1
    shade = x * (maximum + 1) // WIDTH
    distance_squared = (x - WIDTH // 2) ** 2 + (y - HEIGHT // 2) ** 2
    if int(distance_squared**0.5) // 12 % 2 == 0:
        return shade
    return maximum - shade


def image_rows(bits: int) -> list[bytes]:
    """Return the rows of the image, each packed into whole bytes."""
    rows = []
    for y in range(HEIGHT):
        packed = 0
        for x in range(WIDTH):
            packed = (packed << bits) | pixel(x, y, bits)
        rows.append(packed.to_bytes(WIDTH * bits // 8, "big"))
    return rows


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


def content_stream(bits: int) -> bytes:
    image_top = IMAGE_BOTTOM + HEIGHT
    operators = [
        show_text(
            f"PNG predictors with {bits} bit{'s' if bits > 1 else ''} per component",
            REFERENCE_LEFT,
            385,
            18,
        ),
        show_text(
            "Both images must look the same. The left one has no predictor, "
            "the right one uses /Predictor 15,",
            REFERENCE_LEFT,
            362,
            10,
        ),
        show_text(
            "with a different PNG filter for each band of 50 rows. "
            "A decoding error shows as stripes or smears.",
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
                f"{band + 1}: {name}",
                label_left,
                band_top - BAND_HEIGHT / 2 - 3,
                9,
            )
        )
    operators.append(
        show_text(
            f"Image: {WIDTH} x {HEIGHT} pixels, gray, {bits} bit{'s' if bits > 1 else ''} "
            "per component. The Sub, Average and Paeth filters use the byte to the left,",
            REFERENCE_LEFT,
            40,
            9,
        )
    )
    operators.append(
        show_text(
            f"which holds the {8 // bits} pixels to the left: "
            "the bytes per complete pixel are rounded up to one.",
            REFERENCE_LEFT,
            28,
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
    page_count = len(BITS_PER_COMPONENT)
    first_page = 4
    kids = " ".join(f"{first_page + 4 * i} 0 R" for i in range(page_count))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
        b"/Encoding /WinAnsiEncoding >>",
    ]
    for bits in BITS_PER_COMPONENT:
        page = len(objects) + 1
        rows = image_rows(bits)
        image_dictionary = (
            f"/Type /XObject /Subtype /Image /Width {WIDTH} /Height {HEIGHT} "
            f"/ColorSpace /DeviceGray /BitsPerComponent {bits} /Filter /FlateDecode"
        )
        objects += [
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                "/Resources << /Font << /F1 3 0 R >> "
                f"/XObject << /Reference {page + 2} 0 R /Predicted {page + 3} 0 R >> >> "
                f"/Contents {page + 1} 0 R >>"
            ).encode(),
            stream("/Filter /FlateDecode", zlib.compress(content_stream(bits), 9)),
            stream(image_dictionary, zlib.compress(b"".join(rows), 9)),
            stream(
                f"{image_dictionary} /DecodeParms << /Predictor 15 /Colors 1 "
                f"/BitsPerComponent {bits} /Columns {WIDTH} >>",
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
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R "
        f"/ID [<{file_id}> <{file_id}>] >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode()

    with open(OUTPUT, "wb") as f:
        f.write(body)


if __name__ == "__main__":
    main()
