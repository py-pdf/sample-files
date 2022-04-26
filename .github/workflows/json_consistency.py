import datetime
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, NonNegativeInt
from PyPDF2 import PdfFileReader


class PdfEntry(BaseModel):
    path: str
    encrypted: bool
    producer: str
    pages: NonNegativeInt
    images: Optional[NonNegativeInt]
    forms: NonNegativeInt
    creation_date: datetime.datetime


class MainPdfFile(BaseModel):
    data: List[PdfEntry]


def main():
    with open("files.json") as f:
        data = json.load(f)
    main_pdf = MainPdfFile.parse_obj(data)
    registered_pdfs = []

    seen_failure = False
    for entry in main_pdf.data:
        registered_pdfs.append(entry.path)
        if not os.path.exists(entry.path):
            print(f"❌ ERROR: File not found: {entry.path}")
            seen_failure = True
        else:
            print(f"✅ Found {entry.path}")
            check_meta(entry)

    # Are all files registered?
    pdf_paths = Path(".").glob("**/*.pdf")
    for pdf_path in pdf_paths:
        if str(pdf_path) not in registered_pdfs:
            print(f"❌ ERROR: File not registered: {pdf_path}")
            seen_failure = True

    if seen_failure:
        sys.exit(1)


def pdf_to_datetime(date_str):
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


def check_meta(entry: PdfEntry):
    reader = PdfFileReader(entry.path)
    if reader.isEncrypted:
        return
    info = reader.getDocumentInfo()
    if info.get("/Producer") != entry.producer:
        print(
            f"❌ ERROR: Producer mismatch: {entry.producer} vs {info.get('/Producer')}"
        )

    pdf_date = pdf_to_datetime(info.get("/CreationDate")).isoformat()
    entry_date = entry.creation_date.isoformat()[:19]
    if pdf_date != entry_date:
        print(f"❌ ERROR: Creation date mismatch: {entry_date} vs {pdf_date}")
    # if entry.images is not None:
    #     if info.get("/XObject") is None:
    #         if entry.images > 0:
    #             print(f"❌ ERROR: No XObject, but {entry.images} expected")
    #     elif len(info.get("/XObject")) != entry.images:
    #         print(
    #             f"❌ ERROR: XObject count mismatch: {entry.images} vs {len(info.get('/XObject'))}"
    #         )


if __name__ == "__main__":
    main()
