"""Render PDF pages in memory for checking an extracted quotation."""

import math

import pymupdf

from .models import PDFExtractionError


def render_region(page: pymupdf.Page, rect: pymupdf.Rect) -> bytes:
    """Render a selection in page orientation, without annotation overlays.

    Annotation coordinates are unrotated; pixmap clips use rotated page space.
    Bound resolution even for unusually large page selections.
    """
    if not all(math.isfinite(value) for value in rect) or rect.is_empty or rect.is_infinite:
        raise ValueError("Invalid image selection")
    clip = (rect * page.rotation_matrix) & page.rect
    if clip.is_empty:
        raise ValueError("Image selection is outside the page")
    zoom = min(3.0, 2000 / max(clip.width, clip.height))
    return page.get_pixmap(
        matrix=pymupdf.Matrix(zoom, zoom), clip=clip,
        colorspace=pymupdf.csRGB, alpha=False, annots=False,
    ).tobytes("png")


def render_page(data: bytes, page: int, password: str = "") -> bytes:
    """Return a bounded PNG with the original PDF annotations visible."""
    try:
        with pymupdf.open(stream=data, filetype="pdf") as document:
            if document.needs_pass and not document.authenticate(password):
                raise PDFExtractionError("Sayfa önizlemesi için doğru PDF parolası gerekli.")
            if not 1 <= page <= document.page_count:
                raise PDFExtractionError("Önizlenecek sayfa bulunamadı.")
            pdf_page = document[page - 1]
            longest = max(pdf_page.rect.width, pdf_page.rect.height)
            zoom = min(1.7, 1600 / max(longest, 1))
            return pdf_page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False, annots=True).tobytes("png")
    except PDFExtractionError:
        raise
    except Exception as error:
        raise PDFExtractionError("Bu sayfanın önizlemesi oluşturulamadı.") from error
