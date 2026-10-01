"""Render PDF pages in memory for checking an extracted quotation."""

import fitz

from .models import PDFExtractionError


def render_page(data: bytes, page: int, password: str = "") -> bytes:
    """Return a bounded PNG with the original PDF annotations visible."""
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.needs_pass and not document.authenticate(password):
                raise PDFExtractionError("Sayfa önizlemesi için doğru PDF parolası gerekli.")
            if not 1 <= page <= document.page_count:
                raise PDFExtractionError("Önizlenecek sayfa bulunamadı.")
            pdf_page = document[page - 1]
            longest = max(pdf_page.rect.width, pdf_page.rect.height)
            zoom = min(1.7, 1600 / max(longest, 1))
            return pdf_page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False, annots=True).tobytes("png")
    except PDFExtractionError:
        raise
    except Exception as error:
        raise PDFExtractionError("Bu sayfanın önizlemesi oluşturulamadı.") from error
