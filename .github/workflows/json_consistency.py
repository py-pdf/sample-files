import json
from pydantic import BaseModel
from typing import List
import os
import sys

class PdfEntry(BaseModel):
    path: str
    generator: str
    pages: int

class MainPdfFile(BaseModel):
    data: List[PdfEntry]

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
