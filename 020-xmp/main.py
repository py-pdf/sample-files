import io
from fpdf import FPDF
import fitz

# Create a simple PDF using fpdf2
output = io.BytesIO()
pdf = FPDF()
pdf.add_page()
pdf.set_font("Arial", size=12)
pdf.cell(200, 10, txt="Hello, World!", ln=1, align="C")
pdf.output(name=output)
output.seek(0)

# Write the PDF to disk temporarily
input_filename = "input.pdf"
with open(input_filename, "wb") as f:
    f.write(output.read())

# Read the PDF into PyMuPDF
doc = fitz.open(input_filename)

# Set XMP metadata
xmp_metadata = """<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.0-c060 61.134777, 2010/02/12-17:32:00">
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
        <rdf:Description rdf:about=""
            xmlns:dc="http://purl.org/dc/elements/1.1/">
            <dc:creator>
                <rdf:Seq>
                    <rdf:li>John Doe</rdf:li>
                </rdf:Seq>
            </dc:creator>
            <dc:title>
                <rdf:Alt>
                    <rdf:li xml:lang="x-default">Sample PDF with XMP Metadata</rdf:li>
                </rdf:Alt>
            </dc:title>
        </rdf:Description>
    </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""

doc.set_xml_metadata(xmp_metadata)

# Write the PDF with metadata to disk
output_filename = "output_with_metadata_pymupdf.pdf"
doc.save(output_filename)
doc.close()

# Remove the temporary input file
import os

os.remove(input_filename)
