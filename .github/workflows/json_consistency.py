import datetime
import json
import logging
import sys
from pathlib import Path

from pydantic import BaseModel, NonNegativeInt

from pypdf import PdfReader

logger = logging.getLogger()

logger.level = logging.ERROR


class AnnotationCount(BaseModel):
    Highlight: int | None = None
    Ink: int | None = None
    Link: int | None = None
    Text: int | None = None
    Widget: int | None = None

    def items(self) -> list[tuple[str, int]]:
        return [
            ("Highlight", self.Highlight if self.Highlight else 0),
            ("Link", self.Link if self.Link else 0),
            ("Ink", self.Ink if self.Ink else 0),
            ("Text", self.Text if self.Text else 0),
            ("Widget", self.Widget if self.Widget else 0),
        ]

    def sum(self) -> int:
        return sum(value for _, value in self.items())


class PdfEntry(BaseModel):
    path: str
    encrypted: bool
    producer: str | None
    pages: NonNegativeInt
    images: NonNegativeInt | None
    forms: NonNegativeInt
    creation_date: datetime.datetime | None
    annotations: AnnotationCount


class MainPdfFile(BaseModel):
    data: list[PdfEntry]


def main() -> None:
    """Check the consistency of the JSON metadata file."""
    with open("files.json") as f:
        data = json.load(f)
    main_pdf = MainPdfFile.model_validate(data)
    registered_pdfs = []

    seen_failure = False
    for entry in main_pdf.data:
        registered_pdfs.append(entry.path)
        if not Path(entry.path).exists():
            print(f"❌ ERROR: File not found: {entry.path}")
            seen_failure = True
        else:
            print(f"✅ Found {entry.path}")
            seen_failure = seen_failure or check_meta(entry)

    # Are all files registered?
    pdf_paths = Path().glob("**/*.pdf")
    for pdf_path in pdf_paths:
        if str(pdf_path) not in registered_pdfs:
            print(f"❌ ERROR: File not registered: {pdf_path}")
            seen_failure = True

    if seen_failure:
        sys.exit(1)


def pdf_to_datetime(date_str: str | None) -> datetime.datetime | None:
    """Convert a PDF datetime string to a datetime object."""
    if date_str is None:
        return None
    if not date_str.startswith("D:"):
        print(f"❌ ERROR: Invalid date: {date_str}")
    date_str = date_str[2:]
    if len(date_str) < 14:
        print(f"❌ ERROR: Invalid date: {date_str}")
    return datetime.datetime(
        int(date_str[0:4]),  # year
        int(date_str[4:6]),  # month
        int(date_str[6:8]),  # day
        int(date_str[8:10]),  # hour
        int(date_str[10:12]),  # minute
        int(date_str[12:14]),  # second
    )


def get_annotation_counts(reader: PdfReader) -> dict[str, int]:
    """Get a dictionary with the annotation subtype counts."""
    pdf_annotations = {}
    for page in reader.pages:
        if page.annotations:
            for annot in page.annotations:
                annot_obj = annot.get_object()
                subtype = annot_obj["/Subtype"][1:]
                if subtype not in pdf_annotations:
                    pdf_annotations[subtype] = 0
                pdf_annotations[subtype] += 1
    return pdf_annotations


def check_meta(entry: PdfEntry) -> bool:
    """Check if the given entry metadata matches the extracted metadata."""
    seen_failure = False
    try:
        reader = PdfReader(entry.path)
        if reader.is_encrypted:
            return seen_failure
        info = reader.metadata
    except Exception:
        return seen_failure
    if info is None:
        info = {}
    if info.get("/Producer") != entry.producer:
        seen_failure = True
        print(
            f"❌ ERROR: Producer mismatch: {entry.producer} vs {info.get('/Producer')}",
        )
    if len(reader.pages) != entry.pages:
        seen_failure = True
        print(
            f"❌ ERROR: Page mismatch: {len(reader.pages)} vs {entry.pages}",
        )

    pdf_date = pdf_to_datetime(info.get("/CreationDate"))
    pdf_date = None if pdf_date is None else pdf_date.isoformat()
    entry_date = (
        None if entry.creation_date is None else entry.creation_date.isoformat()[:19]
    )
    if pdf_date != entry_date:
        seen_failure = True
        print(f"❌ ERROR: Creation date mismatch: {entry_date} vs {pdf_date}")

    # Check annotations
    pdf_annotations = get_annotation_counts(reader)
    pdf_annotations_sum = sum(pdf_annotations.values())
    entry_annotation_sum = 0
    if entry.annotations:
        entry_annotation_sum = entry.annotations.sum()
    if pdf_annotations_sum != entry_annotation_sum:
        seen_failure = True
        print(
            f"❌ ERROR: Annotation count mismatch: {entry_annotation_sum} vs {pdf_annotations_sum}"
        )
        print("          Expected:")
        seen_subtypes = []
        for subtype, exp_count in sorted(entry.annotations.items()):
            seen_subtypes.append(subtype)
            if exp_count == pdf_annotations.get(subtype, 0):
                continue
            print(
                f"          - {subtype}: {exp_count} vs {pdf_annotations.get(subtype, 0)}"
            )
        todo_subtypes = []
        for subtype, _ in sorted(pdf_annotations.items()):
            if subtype not in seen_subtypes:
                todo_subtypes.append(subtype)
        if todo_subtypes:
            print("          Found:")
            for subtype, count in sorted(pdf_annotations.items()):
                if subtype not in seen_subtypes:
                    todo_subtypes.append(subtype)
                    print(f"          - {subtype}: {count}")
    return seen_failure


if __name__ == "__main__":
    main()
