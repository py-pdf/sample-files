import datetime
import json
import os
import sys
from typing import List

from pydantic import BaseModel, NonNegativeInt


class PdfEntry(BaseModel):
    path: str
    producer: str
    pages: NonNegativeInt
    creation_date: datetime.datetime
    images: NonNegativeInt


class MainPdfFile(BaseModel):
    data: list[PdfEntry]


def main():
    with open("files.json") as f:
        data = json.load(f)
    main_pdf = MainPdfFile.parse_obj(data)

    seen_failure = False
    for entry in main_pdf.data:
        if not os.path.exists(entry.path):
            print(f"File not found: {entry.path}")
            seen_failure = True
        else:
            print(f"Found {entry.path}")
    if seen_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
