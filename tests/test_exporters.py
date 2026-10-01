import csv
import io
import json
from dataclasses import replace

import pytest
from docx import Document
from docx.oxml.ns import qn
from openpyxl import load_workbook

from pdf_notes.exporters import (
    export_csv,
    export_docx,
    export_json,
    export_markdown,
    export_xlsx,
)
from pdf_notes.models import AnnotationRecord


@pytest.fixture
def annotation():
    return AnnotationRecord(
        id="örnek-1",
        filename="Çalışma.pdf",
        document_title="Araştırma ve öğrenme",
        page=3,
        kind="Highlight",
        color_name="Sarı",
        color_hex="#FFFF00",
        quote='İlk satır: “ölçüm”.\nİkinci satır; özgün alıntı.',
        context="Bu paragraf alıntıyı içerir ve daha geniş bağlam sağlar.",
        comment="Burayı tartışma bölümünde karşılaştır.",
        author="Çağrı",
        created="D:20260930123000Z",
        modified="D:20261001103000Z",
        rect=(10.0, 20.0, 300.0, 45.0),
        context_inferred=True,
    )


def test_json_losslessly_retains_text_metadata_and_geometry(annotation):
    data = json.loads(export_json([annotation], metadata={"açıklama": "Seçili notlar"}))
    assert data["version"] == 1
    row = data["records"][0]
    assert row["quote"] == annotation.quote
    assert row["context"] == annotation.context
    assert row["comment"] == annotation.comment
    assert row["color_hex"] == "#FFFF00"
    assert row["author"] == "Çağrı"
    assert row["rect"] == [10.0, 20.0, 300.0, 45.0]
    assert row["context_inferred"] is True
    assert data["metadata"]["açıklama"] == "Seçili notlar"


def test_markdown_groups_documents_and_pages_with_separate_fields(annotation):
    first_page = replace(annotation, id="early", page=1)
    second_document = replace(annotation, id="other", filename="Başka.pdf", document_title="Diğer çalışma")
    content = export_markdown([annotation, second_document, first_page]).decode("utf-8")
    assert content.index("### Sayfa 1") < content.index("### Sayfa 3") < content.index("## Başka")
    # Markdown adds quote markers; removing them reconstructs the original text.
    assert "> " + annotation.quote.replace("\n", "\n> ") in content
    assert "> " + annotation.context in content
    assert "> " + annotation.comment in content
    assert "Not yazarı:** Çağrı" in content
    assert "FFFF00" in content
    assert "konumdan tahmin edildi" in content


def test_csv_bom_turkish_text_and_round_trip(annotation):
    content = export_csv([annotation])
    assert content.startswith(b"\xef\xbb\xbf")
    row = next(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
    assert row["Alıntı / işaretli metin"] == annotation.quote
    assert row["Paragraf bağlamı"] == annotation.context
    assert row["Not / açıklama"] == annotation.comment
    assert row["Not yazarı"] == "Çağrı"
    assert row["PDF dosyası"] == "Çalışma.pdf"
    assert row["Renk kodu"] == "#FFFF00"
    assert row["Sayfa"] == "3"


@pytest.mark.parametrize("payload", ["=HYPERLINK(\"https://example.invalid\")", "+1", "-1", "@SUM(A1)", "   =1", "\t=1", "\r=1", "\x01text", "\x7ftext", "\u200b=1"])
def test_csv_protects_all_user_text_fields_from_formula_injection(annotation, payload):
    modified = replace(annotation, quote=payload, comment=payload, filename=payload, author=payload)
    row = next(csv.DictReader(io.StringIO(export_csv([modified]).decode("utf-8-sig"))))
    for key in ["Alıntı / işaretli metin", "Not / açıklama", "PDF dosyası", "Not yazarı"]:
        assert row[key] == "'" + payload


def test_word_is_valid_contains_grouped_annotations_and_color_shading(annotation):
    earlier = replace(annotation, page=1)
    document = Document(io.BytesIO(export_docx([annotation, earlier])))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert text.index("Sayfa 1") < text.index("Sayfa 3")
    assert annotation.quote in text
    assert annotation.context in text
    assert annotation.comment in text
    assert "Belge başlığı: Araştırma ve öğrenme" in text
    assert "Renk: Sarı (#FFFF00)" in text
    assert "Not yazarı: Çağrı" in text
    quote_paragraph = next(p for p in document.paragraphs if p.text == annotation.quote)
    shading = quote_paragraph._p.find(".//" + qn("w:shd"))
    assert shading is not None
    assert shading.get(qn("w:fill")) == "FFFFBF"


def test_excel_is_valid_and_preserves_literal_formula_text(annotation):
    annotation = replace(annotation, quote="=SUM(A1:A2)", comment="   +1")
    workbook = load_workbook(io.BytesIO(export_xlsx([annotation])), data_only=False)
    worksheet = workbook.active
    assert worksheet.freeze_panes == "A2"
    assert worksheet.auto_filter.ref == "A1:P2"
    assert worksheet["H2"].value == annotation.quote
    assert worksheet["H2"].data_type == "s"
    assert worksheet["J2"].value == annotation.comment
    assert worksheet["J2"].data_type == "s"
    assert worksheet["I2"].value == annotation.context
    assert worksheet["K2"].value == "Çağrı"
    assert worksheet["G2"].fill.fgColor.rgb.endswith("FFFF00")
    assert worksheet["H2"].alignment.wrap_text is True


def test_excel_continues_long_text_without_silent_truncation(annotation):
    quote = "ö" * 32767 + "Son kısım"
    workbook = load_workbook(io.BytesIO(export_xlsx([replace(annotation, quote=quote)])))
    worksheet = workbook.active
    assert worksheet["H2"].value + worksheet["H3"].value == quote
    assert worksheet["P2"].value == "1/2"
    assert worksheet["P3"].value == "2/2"


def test_empty_exports_remain_valid_downloads():
    assert "not bulunamadı" in export_markdown([]).decode("utf-8")
    assert list(csv.DictReader(io.StringIO(export_csv([]).decode("utf-8-sig")))) == []
    assert json.loads(export_json([]))["records"] == []
    assert Document(io.BytesIO(export_docx([]))).paragraphs
    assert load_workbook(io.BytesIO(export_xlsx([]))).active.max_row == 1
