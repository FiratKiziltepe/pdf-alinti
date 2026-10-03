"""Paginated PDF reports with embedded Unicode fonts and image notes."""

from __future__ import annotations

import base64
import html
import io
from pathlib import Path

from .models import AnnotationRecord


def export_pdf(records: list[AnnotationRecord], *, include_context: bool = True) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

    from .exporters import _group_records, _xml_text

    # Bundled OFL fonts cover Turkish, Greek and common scholarly ligatures.
    # No dependency on Windows fonts, external services or temporary files.
    font_dir = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    for name, filename in (("Notes", "NotoSans-Regular.ttf"), ("NotesBold", "NotoSans-Bold.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_dir / filename)))
    pdfmetrics.registerFontFamily("Notes", normal="Notes", bold="NotesBold", italic="Notes", boldItalic="NotesBold")
    body = ParagraphStyle(
        "Body", fontName="Notes", fontSize=10, leading=16,
        textColor=colors.HexColor("#352947"), spaceAfter=10,
        alignment=TA_LEFT, splitLongWords=True,
    )
    title_style = ParagraphStyle("Title", parent=body, fontName="NotesBold", fontSize=21, leading=28, textColor=colors.HexColor("#6D28D9"), spaceAfter=20)
    source_style = ParagraphStyle("Source", parent=body, fontName="NotesBold", fontSize=13, leading=19, spaceBefore=12, keepWithNext=True)
    label_style = ParagraphStyle("Label", parent=body, fontName="NotesBold", fontSize=10, leading=15, spaceAfter=6, keepWithNext=True)
    context_style = ParagraphStyle("Context", parent=body, textColor=colors.HexColor("#78628F"))
    note_style = ParagraphStyle(
        "Note", parent=body, backColor=colors.HexColor("#FFF1EB"),
        textColor=colors.HexColor("#805040"), borderColor=colors.HexColor("#FFE1D4"),
        borderWidth=0.7, borderPadding=10, spaceBefore=12, spaceAfter=20,
    )

    def safe(value: str) -> str:
        return html.escape(_xml_text(value)).replace("\n", "<br/>")

    story = [Paragraph("Alıntılar ve notlar", title_style)]
    if not records:
        story.append(Paragraph("Dışa aktarılacak not bulunamadı.", body))
    for filename, title, pages in _group_records(records):
        story.append(Paragraph(safe(filename), source_style))
        if title and title != filename:
            story.append(Paragraph(safe(title), body))
        for page, page_records in pages:
            story.append(Paragraph(f"Kaynak sayfa {page}", source_style))
            for index, record in enumerate(page_records, start=1):
                story.append(Paragraph(f"{index}. {safe(record.kind)}", label_style))
                if record.author:
                    story.append(Paragraph(f"Not yazarı: {safe(record.author)}", body))
                if record.quote:
                    story.append(Paragraph("Alıntı", label_style))
                    story.append(Paragraph(safe(record.quote), body))
                if record.image_base64:
                    story.append(Paragraph("Alıntı · Çerçeve içindeki alan", label_style))
                    picture = Image(io.BytesIO(base64.b64decode(record.image_base64)))
                    scale = min(460 / picture.imageWidth, 480 / picture.imageHeight)
                    picture.drawWidth = picture.imageWidth * scale
                    picture.drawHeight = picture.imageHeight * scale
                    picture.hAlign = "LEFT"
                    story.extend([picture, Spacer(1, 12)])
                if include_context and record.context:
                    label = "Bağlam (konumdan tahmin edildi)" if record.context_inferred else "Bağlam"
                    story.append(Paragraph(label, label_style))
                    story.append(Paragraph(safe(record.context), context_style))
                if record.comment:
                    story.append(Paragraph(f"<b>Sizin notunuz</b><br/>{safe(record.comment)}", note_style))
                for label, value in (("Oluşturulma tarihi", record.created), ("Değiştirilme tarihi", record.modified)):
                    if value:
                        story.append(Paragraph(f"{label}: {safe(value)}", context_style))
                story.append(Spacer(1, 12))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Notes", 8)
        canvas.setFillColor(colors.HexColor("#78628F"))
        canvas.drawString(48, 28, "Alıntı · PDF not defteri")
        canvas.drawRightString(A4[0] - 48, 28, str(document.page))
        canvas.restoreState()

    stream = io.BytesIO()
    document = SimpleDocTemplate(
        stream, pagesize=A4, leftMargin=48, rightMargin=48,
        topMargin=40, bottomMargin=48, title="Alıntılar ve notlar", author="",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
