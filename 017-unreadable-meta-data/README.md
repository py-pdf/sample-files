# Unreadable metadata

`unreadablemetadata.pdf` is a damaged file, and the damage is deliberate:
it was added to test how a PDF reader handles a document information
dictionary that cannot be read
([pypdf #1279](https://github.com/py-pdf/pypdf/issues/1279),
[pypdf #1298](https://github.com/py-pdf/pypdf/pull/1298)).

## The damage

The file is a linearized PDF 1.4 file of 2,818,798 bytes. The 1,122,166
bytes from offset 1,695,609 to offset 2,817,774 are zero bytes. They
overwrite:

* the end of the stream of object 78, and objects 79 to 174 entirely;
* the beginning of the main cross-reference table at the end of the file:
  the `xref` keyword, the subsection header and the entries of objects 0 to
  126. The entries of objects 127 to 174 remain, but point into the zero
  bytes.

The first-page section at the start of the file is intact: the linearization
parameter dictionary (object 175), the first-page cross-reference table with
objects 175 to 266, its trailer and the catalog (object 176).

## Consequences

* The `/Prev` entry of the first-page trailer points to offset 2,815,238,
  where no cross-reference table can be found any more. Readers have to
  reconstruct the cross-reference table by scanning the file for objects.
* The `/Info` entry of the trailer refers to object 174, which does not
  exist. The document information dictionary, and with it the producer and
  the creation date, cannot be read. pypdf returns `None` for
  `PdfReader.metadata`.
* The `/Pages` entry of the catalog refers to object 172, and the `/Metadata`
  entry to object 173; neither exists. The page tree cannot be read, and
  neither can the XMP metadata. The pages themselves, such as object 1, still
  exist and refer to the missing object 172 as their `/Parent`.

The rest is not damage, but usual for a linearized file: `startxref` of the
first-page trailer is 0, and the trailer of the main cross-reference table
only contains `/Size`.

## Entry in files.json

The entry cannot be checked against the file:

* As the document information dictionary is lost, the producer is not known
  and given as `"?"`. The creation date does not appear anywhere in the file.
* The 4 pages are the number of pages in the linearization parameter
  dictionary (`/N 4`), not the number of pages a reader can find.

`.github/workflows/json_consistency.py` skips the file as long as reading
`PdfReader.metadata` raises an exception, as it does with pypdf 3.17.0.
Newer versions of pypdf return `None` instead, and the check then reports
the producer and the page count as mismatches.
