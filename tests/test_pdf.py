import base64
import io

import pytest

from forge_rag.shared.errors import InvalidDocument


def test_pdf_text_layer_and_page_provenance():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    from forge_rag.pdf.extractor import PDFExtractor

    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=400)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 30 300 Td (Returns are accepted within 30 days.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    sections = PDFExtractor().extract(
        base64.b64encode(buffer.getvalue()).decode(), "application/pdf"
    )
    assert sections[0].page == 1 and "30 days" in sections[0].text


def test_blank_or_corrupt_pdf_rejected():
    from pypdf import PdfWriter

    from forge_rag.pdf.extractor import PDFExtractor

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(InvalidDocument):
        PDFExtractor().extract(base64.b64encode(buffer.getvalue()).decode(), "application/pdf")
    with pytest.raises(InvalidDocument):
        PDFExtractor().extract("not-base64", "application/pdf")
