# Test PDF document sample with cropbox, rotation and scaling
#
# SPDX-FileCopyrightText: 2026 Robert Wolff <mahlzahn@posteo.de>
# SPDX-License-Identifier: CC-BY-SA-4.0

import pymupdf
import pypdf

def insert_stuff(page, label, rect):
    page.draw_rect(rect, fill=(0, 1, 0), fill_opacity=0.5)
    page.insert_image((rect.x0 + 50, rect.y0, rect.x1, rect.y1), filename='censor.png')
    page.insert_text((rect.x0 + 5, rect.y0 + 15), label, color=(0, 0, 1))
    page.insert_link({'from': pymupdf.Rect(rect.x1 - 20, rect.y0, rect.x1, rect.y1),
                      'uri': 'https://codeberg.org/censor/Censor',
                      'kind': 2})
    text_annot = page.add_text_annot((rect.x0, rect.y0), f'annotation {label} {page.number}')
    file_annot = page.add_file_annot((rect.x0, rect.y1), label.encode(), f'file {label} {page.number}.txt')
    page.add_highlight_annot(clip=(rect.x0 + 40, rect.y0, rect.x1, rect.y1))
    polygon_annot = page.add_polygon_annot([pymupdf.Point(rect.x0 + 20, rect.y0 + 5),
                                            pymupdf.Point(rect.x0 + 25, rect.y0),
                                            pymupdf.Point(rect.x0 + 30, rect.y0 + 5)])
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = f'checkbox {label} {page.number}'
    widget.field_value = True
    widget.rect = pymupdf.Rect(rect.x0 + 30, rect.y0, rect.x0 + 40, rect.y0 + 10)
    widget.border_width = 1
    widget.border_color = (0, 0, 0)
    page.add_widget(widget)
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = f'text widget {label} {page.number}'
    widget.field_value = label
    widget.rect = pymupdf.Rect(rect.x0 + 20, rect.y1, rect.x0 + 50, rect.y1 + 10)
    widget.border_width = 1
    widget.border_color = (0, 0, 0)
    page.add_widget(widget)

def insert_corner_stuff(page, rect):
    page.draw_rect(rect, fill=(0, 1, 0), width=0)
    page.insert_image(rect, filename='censor.png')
    page.insert_link({'from': rect,
                      'uri': 'https://codeberg.org/censor/Censor',
                      'kind': 2})
    page.add_polygon_annot([pymupdf.Point(rect.x0 + 1, rect.y0 + 1),
                            pymupdf.Point(rect.x1 - 1, rect.y1 - 1)])
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = f'checkbox {rect} {page}'
    widget.field_value = True
    widget.rect = rect
    widget.border_width = 0.5
    widget.border_color = (0, 0, 0)
    page.add_widget(widget)

document = pymupdf.Document()

for rotation in [0, 90, 180, 270]:
    page = document.new_page()
    page.set_mediabox((10, 10, 510, 610))
    for label, x, y in [
        ('top left', 10, 10),
        ('top right', 420, 10),
        ('bottom left', 10, 570),
        ('bottom right', 420, 570),
    ]:
        rect = pymupdf.Rect(x, y, x + 70, y + 20)
        insert_stuff(page, 'x ' + label, pymupdf.Rect(rect))
        rect_inside = pymupdf.Rect(*(r + 100 if r < 250 else r - 100 for r in rect))
        insert_stuff(page, label, pymupdf.Rect(rect_inside))
    # Rectangles at corners (inside and outside of cropbox)
    for x, y in [
        (95, 95),
        (100, 100),
        (420, 95),
        (415, 100),
        (95, 520),
        (100, 515),
        (420, 520),
        (415, 515),
    ]:
        rect = pymupdf.Rect(x, y, x + 5, y + 5)
        insert_corner_stuff(page, rect)
    page.set_cropbox((110, 100, 430, 520))
    page.set_rotation(rotation)

file_name = 'cropped-rotated-scaled.pdf'
document.save(file_name)

# Scale pages
reader = pypdf.PdfReader(file_name)
writer = pypdf.PdfWriter()
for (scale_x, scale_y), page in zip(
        [(1.2, 1.2), (0.9, 0.9), (1.1, 0.7), (1.1, 1.3)],
        reader.pages):
    page.scale(scale_x, scale_y)
    writer.add_page(page)
with open(file_name, 'wb') as file:
    writer.write(file)
