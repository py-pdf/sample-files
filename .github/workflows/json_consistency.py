import datetime
import json
import os
import sys
from pathlib import Path
from typing import List

from pydantic import BaseModel, NonNegativeInt


class PdfEntry(BaseModel):
    path: str
    encrypted: bool
    producer: str
    pages: NonNegativeInt
    images: NonNegativeInt
    forms: NonNegativeInt
    creation_date: datetime.datetime


class MainPdfFile(BaseModel):
    data: list[PdfEntry]


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

    # Are all files registered?
    pdf_paths = Path(".").glob("**/*.pdf")
    for pdf_path in pdf_paths:
        if str(pdf_path) not in registered_pdfs:
            print(f"❌ ERROR: File not registered: {pdf_path}")
            seen_failure = True

    if seen_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
