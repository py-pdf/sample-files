"""
Create a small tagged PDF 2.0 file with a hand-written structure tree.

The file is written without any PDF library, so that every object is under
control. It contains:

* a structure tree with a role map, an ID tree and a parent tree
  (ISO 32000-2:2020, 14.7);
* marked content on pages and inside a form XObject, an image XObject and two
  link annotations as content items;
* structure destinations (/SD) in the actions of the links and of an outline
  item (ISO 32000-2:2020, 12.3.2.3), and outline items with /SE;
* a paragraph that spans two pages;
* headers and footers marked as artifacts.

The font is the standard font Helvetica, which is not embedded, so the file
does not conform to PDF/UA.

Usage: python create_tagged_pdf.py
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Union

OUTPUT = "tagged.pdf"

# Glyph widths of Helvetica for the character codes 32 to 126 in
# WinAnsiEncoding, taken from the Adobe Font Metrics file of the font.
HELVETICA_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
LEFT = 72


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


def text_width(text: str, size: float) -> float:
    return sum(HELVETICA_WIDTHS[ord(char) - 32] for char in text) * size / 1000


class Document:
    def __init__(self) -> None:
        self.objects: dict[int, PdfValue] = {}

    def reserve(self) -> Ref:
        ref = Ref(len(self.objects) + 1)
        self.objects[ref.number] = None
        return ref

    def set(self, ref: Ref, value: PdfValue) -> Ref:
        self.objects[ref.number] = value
        return ref

    def add(self, value: PdfValue) -> Ref:
        return self.set(self.reserve(), value)

    def write(self, path: str, root: Ref) -> None:
        body = bytearray(b"%PDF-2.0\n%\xe2\xe3\xcf\xd3\n")
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


def show_text(text: str, x: float, y: float, size: float) -> str:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return f"BT /F1 {size} Tf {x:.3f} {y:.3f} Td ({escaped}) Tj ET\n"


def marked(tag: str, mcid: int, operators: str) -> str:
    return f"/{tag} <</MCID {mcid}>> BDC\n{operators}EMC\n"


def artifacts(page_number: int) -> str:
    header = show_text("Tagged PDF sample", LEFT, 800, 9)
    footer = show_text(f"Page {page_number} of 3", LEFT, 40, 9)
    return (
        f"/Artifact <</Type /Pagination /Subtype /Header>> BDC\n{header}EMC\n"
        f"/Artifact <</Type /Pagination /Subtype /Footer>> BDC\n{footer}EMC\n"
    )


def main() -> None:
    doc = Document()

    catalog = doc.reserve()
    pages = doc.reserve()
    page_1, page_2, page_3 = doc.reserve(), doc.reserve(), doc.reserve()
    struct_tree_root = doc.reserve()
    document = doc.reserve()
    chapter_1, chapter_2 = doc.reserve(), doc.reserve()
    heading_1, paragraph_1, link_1 = doc.reserve(), doc.reserve(), doc.reserve()
    heading_2, figure, spanning_paragraph = doc.reserve(), doc.reserve(), doc.reserve()
    form_paragraph, link_paragraph, link_2 = doc.reserve(), doc.reserve(), doc.reserve()

    widths = doc.add(HELVETICA_WIDTHS)
    font_descriptor = doc.add({
        "Type": Name("FontDescriptor"),
        "FontName": Name("Helvetica"),
        "Flags": 32,
        "FontBBox": [-166, -225, 1000, 931],
        "ItalicAngle": 0,
        "Ascent": 718,
        "Descent": -207,
        "CapHeight": 718,
        "XHeight": 523,
        "StemV": 88,
    })
    font = doc.add({
        "Type": Name("Font"),
        "Subtype": Name("Type1"),
        "BaseFont": Name("Helvetica"),
        "Encoding": Name("WinAnsiEncoding"),
        "FirstChar": 32,
        "LastChar": 126,
        "Widths": widths,
        "FontDescriptor": font_descriptor,
    })

    # Page 1: heading and a paragraph with a link to the figure on page 2.
    before, link_text, after = "This paragraph links to ", "the figure on page 2", "."
    link_x = LEFT + text_width(before, 12)
    after_x = link_x + text_width(link_text, 12)
    content_1 = doc.add(Stream({}, (
        artifacts(1)
        + marked("H1", 0, show_text("Structure destinations", LEFT, 750, 20))
        + marked("P", 1, show_text(before, LEFT, 710, 12))
        + marked("Link", 2, show_text(link_text, link_x, 710, 12))
        + marked("P", 3, show_text(after, after_x, 710, 12))
    ).encode("latin-1")))
    annotation_1 = doc.add({
        "Type": Name("Annot"),
        "Subtype": Name("Link"),
        "Rect": [link_x, 706, after_x, 722],
        "Border": [0, 0, 0],
        "Contents": "Go to the figure on page 2",
        "P": page_1,
        "A": {
            "S": Name("GoTo"),
            "D": [page_2, Name("XYZ"), LEFT, 800, None],
            "SD": [figure, Name("XYZ"), LEFT, 800, None],
        },
        "StructParent": 1,
    })

    # Page 2: heading, an image that is a content item on its own and the
    # start of a paragraph that continues on page 3.
    image = doc.add(Stream({
        "Type": Name("XObject"),
        "Subtype": Name("Image"),
        "Width": 4,
        "Height": 2,
        "ColorSpace": Name("DeviceRGB"),
        "BitsPerComponent": 8,
        "StructParent": 3,
    }, bytes([
        230, 25, 75, 60, 180, 75, 255, 225, 25, 0, 130, 200,
        245, 130, 48, 145, 30, 180, 70, 240, 240, 240, 50, 230,
    ])))
    content_2 = doc.add(Stream({}, (
        artifacts(2)
        + marked("H1", 0, show_text("A figure", LEFT, 750, 20))
        + f"q 200 0 0 100 {LEFT} 620 cm /Im1 Do Q\n"
        + marked("P", 1, show_text("This paragraph starts on page 2 and", LEFT, 580, 12))
    ).encode("latin-1")))

    # Page 3: the end of the paragraph, text drawn by a form XObject and a link
    # back to the heading on page 1.
    form = doc.add(Stream({
        "Type": Name("XObject"),
        "Subtype": Name("Form"),
        "BBox": [0, 0, PAGE_WIDTH - 2 * LEFT, 30],
        "Resources": {"Font": {"F1": font}},
        "StructParents": 5,
    }, marked("P", 0, show_text("This text is drawn by a form XObject.", 0, 10, 12)).encode("latin-1")))
    back_text = "Back to the first page"
    content_3 = doc.add(Stream({}, (
        artifacts(3)
        + marked("P", 0, show_text("continues on page 3.", LEFT, 750, 12))
        + f"q 1 0 0 1 {LEFT} 690 cm /Fm1 Do Q\n"
        + marked("Link", 1, show_text(back_text, LEFT, 650, 12))
    ).encode("latin-1")))
    annotation_2 = doc.add({
        "Type": Name("Annot"),
        "Subtype": Name("Link"),
        "Rect": [LEFT, 646, LEFT + text_width(back_text, 12), 662],
        "Border": [0, 0, 0],
        "Contents": "Go to the heading on page 1",
        "P": page_3,
        "A": {
            "S": Name("GoTo"),
            "D": [page_1, Name("XYZ"), LEFT, 800, None],
            "SD": [heading_1, Name("XYZ"), LEFT, 800, None],
        },
        "StructParent": 6,
    })

    def page(content: Ref, struct_parents: int, annotations: list[Ref], xobjects: dict[str, Ref]) -> dict:
        resources: dict[str, PdfValue] = {"Font": {"F1": font}}
        if xobjects:
            resources["XObject"] = xobjects
        dictionary: dict[str, PdfValue] = {
            "Type": Name("Page"),
            "Parent": pages,
            "MediaBox": [0, 0, PAGE_WIDTH, PAGE_HEIGHT],
            "Resources": resources,
            "Contents": content,
            "StructParents": struct_parents,
        }
        if annotations:
            dictionary["Annots"] = annotations
            dictionary["Tabs"] = Name("S")
        return dictionary

    doc.set(page_1, page(content_1, 0, [annotation_1], {}))
    doc.set(page_2, page(content_2, 2, [], {"Im1": image}))
    doc.set(page_3, page(content_3, 4, [annotation_2], {"Fm1": form}))
    doc.set(pages, {"Type": Name("Pages"), "Kids": [page_1, page_2, page_3], "Count": 3})

    def element(structure_type: str, parent: Ref, kids: PdfValue, **entries: PdfValue) -> dict:
        return {"Type": Name("StructElem"), "S": Name(structure_type), "P": parent, "K": kids, **entries}

    doc.set(document, element("Document", struct_tree_root, [chapter_1, chapter_2]))
    # "Chapter" is a custom structure type that the role map maps to "Sect".
    doc.set(chapter_1, element("Chapter", document, [heading_1, paragraph_1], T="Structure destinations"))
    doc.set(heading_1, element("H1", chapter_1, 0, Pg=page_1))
    doc.set(paragraph_1, element("P", chapter_1, [1, link_1, 3], Pg=page_1))
    doc.set(link_1, element("Link", paragraph_1, [2, {"Type": Name("OBJR"), "Obj": annotation_1}], Pg=page_1))
    doc.set(chapter_2, element(
        "Chapter", document, [heading_2, figure, spanning_paragraph, form_paragraph, link_paragraph], T="A figure"
    ))
    doc.set(heading_2, element("H1", chapter_2, 0, Pg=page_2))
    doc.set(figure, element(
        "Figure",
        chapter_2,
        {"Type": Name("OBJR"), "Obj": image},
        Pg=page_2,
        ID=b"figure-1",
        Alt="Eight coloured squares in two rows",
        A={"O": Name("Layout"), "BBox": [LEFT, 620, LEFT + 200, 720]},
    ))
    doc.set(spanning_paragraph, element("P", chapter_2, [
        {"Type": Name("MCR"), "Pg": page_2, "MCID": 1},
        {"Type": Name("MCR"), "Pg": page_3, "MCID": 0},
    ]))
    doc.set(form_paragraph, element("P", chapter_2, {"Type": Name("MCR"), "Stm": form, "MCID": 0}, Pg=page_3))
    doc.set(link_paragraph, element("P", chapter_2, [link_2]))
    doc.set(link_2, element("Link", link_paragraph, [1, {"Type": Name("OBJR"), "Obj": annotation_2}], Pg=page_3))

    parent_tree = doc.add({"Nums": [
        0, [heading_1, paragraph_1, link_1, paragraph_1],  # page 1, by MCID
        1, link_1,  # link annotation on page 1
        2, [heading_2, spanning_paragraph],  # page 2, by MCID
        3, figure,  # image on page 2
        4, [spanning_paragraph, link_2],  # page 3, by MCID
        5, [form_paragraph],  # form XObject on page 3, by MCID
        6, link_2,  # link annotation on page 3
    ]})
    id_tree = doc.add({"Names": [b"figure-1", figure]})
    doc.set(struct_tree_root, {
        "Type": Name("StructTreeRoot"),
        "K": [document],
        "ParentTree": parent_tree,
        "ParentTreeNextKey": 7,
        "IDTree": id_tree,
        "RoleMap": {"Chapter": Name("Sect")},
    })

    outlines = doc.reserve()
    outline_1, outline_2 = doc.reserve(), doc.reserve()
    doc.set(outlines, {"Type": Name("Outlines"), "First": outline_1, "Last": outline_2, "Count": 2})
    doc.set(outline_1, {
        "Title": "Structure destinations",
        "Parent": outlines,
        "Next": outline_2,
        "Dest": [page_1, Name("XYZ"), LEFT, 800, None],
        "SE": heading_1,
    })
    doc.set(outline_2, {
        "Title": "A figure",
        "Parent": outlines,
        "Prev": outline_1,
        "A": {
            "S": Name("GoTo"),
            "D": [page_2, Name("XYZ"), LEFT, 800, None],
            "SD": [heading_2, Name("XYZ"), LEFT, 800, None],
        },
        "SE": heading_2,
    })

    doc.set(catalog, {
        "Type": Name("Catalog"),
        "Pages": pages,
        "StructTreeRoot": struct_tree_root,
        "MarkInfo": {"Marked": True},
        "Lang": "en-US",
        "Outlines": outlines,
    })
    doc.write(OUTPUT, catalog)


if __name__ == "__main__":
    main()
