"""Generated PDFs exercise selection geometry and preservation of note data."""

import re

import fitz
import pytest

from pdf_notes.extract import extract_pdf
from pdf_notes.models import PDFExtractionError


def _pdf(*, encrypted=False):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Research result supports the hypothesis.", fontsize=12)
    doc.set_metadata({"title": "Research paper"})
    annot = page.add_highlight_annot(page.search_for("Research result", quads=True))
    annot.set_info(content="Compare with the second experiment.", title="Ada", creationDate="D:20260929123456+03'00'", modDate="D:20260930110000Z")
    annot.update()
    data = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner-secret", user_pw="read-secret") if encrypted else doc.tobytes()
    doc.close()
    return data


def test_quote_comment_metadata_context_and_stable_ids():
    data = _pdf()
    result = extract_pdf(data, "paper.pdf")
    assert result.page_count == 1
    assert result.title == "Research paper"
    assert result.warnings == []
    assert len(result.records) == 1
    record = result.records[0]
    assert record.quote == "Research result"
    assert record.comment == "Compare with the second experiment."
    assert record.context == "Research result supports the hypothesis."
    assert record.context_inferred is True
    assert record.document_title == "Research paper"
    assert record.author == "Ada"
    assert record.created == "2026-09-29T12:34:56+03:00"
    assert record.modified == "2026-09-30T11:00:00+00:00"
    assert record.page == 1
    assert record.kind == "Vurgulama"
    assert (record.color_name, record.color_hex) == ("Sarı", "#FFFF00")
    assert record.id == extract_pdf(data, "paper.pdf").records[0].id
    assert record.id != extract_pdf(data, "another-file.pdf").records[0].id


@pytest.mark.parametrize("rgb, name, expected_hex", [
    ((1, 0, 0), "Kırmızı", "#FF0000"),
    ((0, 1, 0), "Yeşil", "#00FF00"),
    ((0, 0, 1), "Mavi", "#0000FF"),
    ((0.5, 0, 1), "Mor", "#8000FF"),
    ((1, 0.5, 0), "Turuncu", "#FF8000"),
    ((1, 0, 1), "Pembe", "#FF00FF"),
    ((1, 0.75, 0.8), "Pembe", "#FFBFCC"),
    ((0.5, 0, 0.5), "Mor", "#800080"),
    ((0.89, 0.95, 0.93), "Yeşil", "#E3F2ED"),
    ((0.5, 0.5, 0.5), "Gri", "#808080"),
])
def test_actual_annotation_colors(rgb, name, expected_hex):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Colored quotation")
    annot = page.add_highlight_annot(page.search_for("Colored"))
    annot.set_colors(stroke=rgb)
    annot.update()
    record = extract_pdf(doc.tobytes(), "colors.pdf").records[0]
    assert record.color_name == name
    assert record.color_hex == expected_hex
    assert re.fullmatch(r"#[0-9A-F]{6}", record.color_hex)
    doc.close()


def test_disjoint_quadpoints_exclude_rectangle_contents_and_other_column():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "First selected", fontsize=12)
    page.insert_text((330, 72), "OTHER COLUMN BAIT", fontsize=12)
    page.insert_text((72, 108), "UNSELECTED LINE BAIT", fontsize=12)
    page.insert_text((330, 144), "Second selected", fontsize=12)
    quads = page.search_for("First selected", quads=True) + page.search_for("Second selected", quads=True)
    annot = page.add_highlight_annot(quads)
    annot.update()
    record = extract_pdf(doc.tobytes(), "columns.pdf").records[0]
    assert record.quote == "First selected\nSecond selected"
    assert "BAIT" not in record.quote
    assert "BAIT" not in record.context
    doc.close()


def test_disjoint_segments_on_same_line_do_not_fill_unmarked_gap():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "FIRST unmarked middle LAST", fontsize=12)
    page.add_highlight_annot(page.search_for("FIRST", quads=True) + page.search_for("LAST", quads=True))
    record = extract_pdf(doc.tobytes(), "segments.pdf").records[0]
    assert record.quote == "FIRST … LAST"
    assert "unmarked middle" in record.context
    doc.close()


@pytest.mark.parametrize("method, kind", [
    ("add_underline_annot", "Altı çizili"),
    ("add_squiggly_annot", "Dalgalı alt çizgi"),
    ("add_strikeout_annot", "Üstü çizili"),
])
def test_line_markup_does_not_capture_adjacent_lines(method, kind):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Only this line", fontsize=12)
    page.insert_text((72, 86), "Do not include me", fontsize=12)
    annot = getattr(page, method)(page.search_for("Only this line", quads=True))
    annot.set_info(content="A comment on the marked passage")
    annot.update()
    record = extract_pdf(doc.tobytes(), "lines.pdf").records[0]
    assert record.quote == "Only this line"
    assert record.kind == kind
    assert record.comment == "A comment on the marked passage"
    doc.close()


@pytest.mark.parametrize("page_rotation, text_rotation", [(90, 0), (0, 90), (0, 270)])
def test_rotated_pages_and_vertical_text(page_rotation, text_rotation):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((200, 240), "Rotated quotation", rotate=text_rotation, fontsize=12)
    page.add_highlight_annot(page.search_for("Rotated quotation", quads=True))
    page.set_rotation(page_rotation)
    record = extract_pdf(doc.tobytes(), "rotated.pdf").records[0]
    assert record.quote == "Rotated quotation"
    doc.close()


def test_diagonal_quad_selects_rotated_characters():
    doc = fitz.open()
    page = doc.new_page()
    point = fitz.Point(200, 240)
    page.insert_text(point, "Diagonal quotation", fontsize=12, morph=(point, fitz.Matrix(1, 1).prerotate(35)))
    page.add_highlight_annot(page.search_for("Diagonal quotation", quads=True))
    record = extract_pdf(doc.tobytes(), "diagonal.pdf").records[0]
    assert record.quote == "Diagonal quotation"
    doc.close()


def test_sticky_notes_have_inferred_paragraph_and_never_invent_quotes():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "The paragraph associated with the note.", fontsize=12)
    page.insert_text((72, 300), "A different paragraph far below.", fontsize=12)
    annot = page.add_text_annot((55, 62), "Read the original source.")
    annot.set_info(title="Grace")
    annot.update()
    record = extract_pdf(doc.tobytes(), "note.pdf").records[0]
    assert record.quote == ""
    assert record.context == "The paragraph associated with the note."
    assert record.context_inferred is True
    assert record.comment == "Read the original source."
    assert record.author == "Grace"
    assert record.kind == "Not"
    doc.close()


def test_free_text_is_exported_as_comment():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Existing paragraph", fontsize=12)
    page.add_freetext_annot(fitz.Rect(72, 85, 260, 120), "An explanation added to the PDF", fontsize=10)
    result = extract_pdf(doc.tobytes(), "freetext.pdf")
    assert len(result.records) == 1
    assert result.records[0].kind == "Serbest metin"
    assert result.records[0].comment == "An explanation added to the PDF"
    assert result.records[0].quote == ""
    assert result.records[0].context == "Existing paragraph"
    doc.close()


def test_free_text_appearances_cannot_contaminate_underlying_quote():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Original source", fontsize=12)
    selection = page.search_for("Original source", quads=True)
    page.add_freetext_annot(fitz.Rect(72, 59, 250, 78), "OVERLAY NOTE", fontsize=12)
    page.add_highlight_annot(selection)
    result = extract_pdf(doc.tobytes(), "overlay.pdf")
    highlight = next(record for record in result.records if record.kind == "Vurgulama")
    assert highlight.quote == "Original source"
    assert highlight.context == "Original source"
    assert "OVERLAY" not in highlight.quote
    doc.close()


def test_note_paragraph_context_prefers_body_text_over_page_footer():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 580), "A nearby source paragraph", fontsize=12)
    page.insert_text((72, 790), "Page footer", fontsize=9)
    page.add_freetext_annot(fitz.Rect(72, 650, 260, 720), "A note near the bottom", fontsize=10)
    record = extract_pdf(doc.tobytes(), "footer.pdf").records[0]
    assert record.context == "A nearby source paragraph"
    assert record.context_inferred is True
    doc.close()


def test_nested_replies_attach_to_original_note_without_duplicate_records():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Selected passage", fontsize=12)
    parent = page.add_highlight_annot(page.search_for("Selected passage"))
    parent.set_info(content="Original comment")
    parent.update()
    reply = page.add_text_annot((55, 62), "First reply")
    reply.set_info(title="Reviewer A", creationDate="D:20260930120000Z")
    reply.update()
    doc.xref_set_key(reply.xref, "IRT", f"{parent.xref} 0 R")
    doc.xref_set_key(reply.xref, "RT", "/R")
    nested = page.add_text_annot((55, 95), "Nested reply")
    nested.set_info(title="Reviewer B")
    nested.update()
    doc.xref_set_key(nested.xref, "IRT", f"{reply.xref} 0 R")
    result = extract_pdf(doc.tobytes(), "replies.pdf")
    assert len(result.records) == 1
    record = result.records[0]
    assert record.quote == "Selected passage"
    assert record.comment == "Original comment\n\nYanıt (Reviewer A · 2026-09-30T12:00:00+00:00): First reply\n\nYanıt (Reviewer B): Nested reply"
    doc.close()


def test_orphan_reply_is_preserved_with_warning():
    doc = fitz.open()
    page = doc.new_page()
    reply = page.add_text_annot((55, 62), "Unattached comment")
    reply.update()
    doc.xref_set_key(reply.xref, "IRT", "999 0 R")
    result = extract_pdf(doc.tobytes(), "orphan.pdf")
    assert len(result.records) == 1
    assert result.records[0].comment == "Unattached comment"
    assert any("ana nota bağlanamadı" in warning for warning in result.warnings)
    doc.close()


def test_grouped_markup_keeps_each_selection_instead_of_losing_child_quote():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "First selection")
    page.insert_text((72, 110), "Second selection")
    first = page.add_highlight_annot(page.search_for("First selection"))
    second = page.add_highlight_annot(page.search_for("Second selection"))
    doc.xref_set_key(second.xref, "IRT", f"{first.xref} 0 R")
    doc.xref_set_key(second.xref, "RT", "/Group")
    result = extract_pdf(doc.tobytes(), "grouped.pdf")
    assert [record.quote for record in result.records] == ["First selection", "Second selection"]
    doc.close()


def test_password_missing_wrong_and_correct():
    data = _pdf(encrypted=True)
    with pytest.raises(PDFExtractionError, match="parola korumalı"):
        extract_pdf(data, "locked.pdf")
    with pytest.raises(PDFExtractionError, match="parolası yanlış"):
        extract_pdf(data, "locked.pdf", "wrong-secret")
    result = extract_pdf(data, "locked.pdf", "read-secret")
    assert result.records[0].quote == "Research result"


@pytest.mark.parametrize("data", [b"", b"This is not a PDF", b"%PDF-1.7\ntruncated"])
def test_unreadable_files_have_clear_errors(data):
    with pytest.raises(PDFExtractionError, match="PDF"):
        extract_pdf(data, "invalid.pdf")


def test_scan_and_flattened_annotations_have_actionable_warning():
    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(72, 72, 150, 92), color=(1, 1, 0), fill=(1, 1, 0))
    result = extract_pdf(doc.tobytes(), "scan.pdf")
    assert result.records == []
    assert any("OCR" in warning for warning in result.warnings)
    assert any("birleştirilmiş" in warning for warning in result.warnings)
    doc.close()


def test_markups_without_text_keep_comment_and_warn():
    doc = fitz.open()
    page = doc.new_page()
    annot = page.add_highlight_annot(fitz.Rect(72, 72, 160, 92))
    annot.set_info(content="A useful note on an image")
    annot.update()
    result = extract_pdf(doc.tobytes(), "image.pdf")
    assert result.records[0].quote == ""
    assert result.records[0].comment == "A useful note on an image"
    assert result.records[0].context_inferred is False
    assert any("seçili metni bulunamadı" in warning for warning in result.warnings)
    doc.close()


def test_records_have_one_based_page_numbers_and_unique_ids():
    doc = fitz.open()
    for index in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {index + 1}")
        page.add_highlight_annot(page.search_for("Page"))
    result = extract_pdf(doc.tobytes(), "pages.pdf")
    assert [record.page for record in result.records] == [1, 2]
    assert len({record.id for record in result.records}) == 2
    doc.close()


def test_one_broken_annotation_does_not_discard_other_notes(monkeypatch):
    data = _pdf()
    original = fitz.Page.load_annot
    calls = 0

    def sometimes_broken(page, xref):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("Damaged annotation")
        return original(page, xref)

    doc = fitz.open(stream=data, filetype="pdf")
    page = doc[0]
    page.add_text_annot((55, 85), "Surviving comment")
    data = doc.tobytes()
    doc.close()
    monkeypatch.setattr(fitz.Page, "load_annot", sometimes_broken)
    result = extract_pdf(data, "damaged-note.pdf")
    assert [record.comment for record in result.records] == ["Surviving comment"]
    assert any("bir not okunamadı" in warning for warning in result.warnings)
