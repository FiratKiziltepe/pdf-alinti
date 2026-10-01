"""Extract PDF annotation text without treating nearby text as an exact quote.

PDF markup QuadPoints are matched against character centres.  A markup's
bounding rectangle alone may cover unrelated columns or intervening lines.
Paragraph context comes from PDF text blocks and is explicitly inferred.
"""

from __future__ import annotations

import colorsys
import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz

from .models import AnnotationRecord, ExtractionResult, PDFExtractionError


_MARKUP_TYPES = {8, 9, 10, 11}
_KINDS = {
    0: "Not",
    2: "Serbest metin",
    3: "Çizgi",
    4: "Dikdörtgen",
    5: "Elips",
    6: "Çokgen",
    7: "Çoklu çizgi",
    8: "Vurgulama",
    9: "Altı çizili",
    10: "Dalgalı alt çizgi",
    11: "Üstü çizili",
    12: "Karartma",
    13: "Damga",
    14: "Düzeltme işareti",
    15: "Çizim",
    17: "Dosya eki",
    18: "Ses notu",
    19: "Video notu",
}


@dataclass
class _Character:
    text: str
    center: tuple[float, float]


@dataclass
class _Line:
    chars: list[_Character]
    block: int


@dataclass
class _Block:
    rect: fitz.Rect
    text: str


@dataclass
class _PageText:
    lines: list[_Line]
    blocks: list[_Block]


@dataclass
class _ContextGroup:
    rect: fitz.Rect
    direction: tuple[float, float]
    lines: list[list[_Character]]


def _along_interval(rect: fitz.Rect, direction: tuple[float, float]) -> tuple[float, float]:
    projections = [point.x * direction[0] + point.y * direction[1]
                   for point in (rect.tl, rect.tr, rect.bl, rect.br)]
    return min(projections), max(projections)


def _page_text(page: fitz.Page) -> _PageText:
    lines: list[_Line] = []
    blocks: list[_Block] = []
    # MuPDF page text can include FreeText annotation appearances. A display
    # list of page contents alone avoids promoting comments into source text.
    # Like Page.get_textpage(), use unrotated coordinates for QuadPoints.
    rotation = page.rotation
    if rotation:
        page.set_rotation(0)
    try:
        text_page = page.get_displaylist(annots=False).get_textpage(fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)
        if not hasattr(text_page, "extractRAWDICT"):
            text_page = fitz.TextPage(text_page)
        raw = text_page.extractRAWDICT()
    finally:
        if rotation:
            page.set_rotation(rotation)
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        groups: list[_ContextGroup] = []
        for line in block.get("lines", []):
            chars: list[_Character] = []
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    rect = fitz.Rect(char["bbox"])
                    chars.append(_Character(char["c"], ((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)))
            if not chars:
                continue
            line_rect = fitz.Rect(line["bbox"])
            direction = tuple(line.get("dir", (1.0, 0.0)))
            start, end = _along_interval(line_rect, direction)
            matching_groups = []
            for group in groups:
                if sum(first * second for first, second in zip(direction, group.direction)) < 0.95:
                    continue
                group_start, group_end = _along_interval(group.rect, direction)
                overlap = min(end, group_end) - max(start, group_start)
                if overlap > 0.12 * min(end - start, group_end - group_start):
                    matching_groups.append(group)
            if matching_groups:
                group = min(matching_groups, key=lambda candidate: abs(candidate.rect.y1 - line_rect.y0) + abs(candidate.rect.x0 - line_rect.x0))
                group.rect |= line_rect
                group.lines.append(chars)
            else:
                groups.append(_ContextGroup(line_rect, direction, [chars]))
        # MuPDF can combine side-by-side column lines into one native block.
        # Split non-overlapping reading intervals before deriving context.
        for group in groups:
            block_index = len(blocks)
            texts = []
            for chars in group.lines:
                text = "".join(char.text for char in chars).strip()
                if text:
                    texts.append(text)
                lines.append(_Line(chars, block_index))
            blocks.append(_Block(group.rect, " ".join(texts)))
    return _PageText(lines, blocks)


def _inside_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    """Test a convex QuadPoints polygon, including its boundary."""
    signs = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        cross = (end[0] - start[0]) * (point[1] - start[1]) - (end[1] - start[1]) * (point[0] - start[0])
        # PDF round trips can move edges a small fraction of a point.
        tolerance = 0.05 * max(1.0, math.hypot(end[0] - start[0], end[1] - start[1]))
        if abs(cross) > tolerance:
            signs.append(cross > 0)
    return bool(signs) and (all(signs) or not any(signs))


def _marked_text(annot: fitz.Annot, page_text: _PageText) -> tuple[str, str]:
    vertices = annot.vertices or []
    polygons = []
    for index in range(0, len(vertices) - 3, 4):
        # PDF order is upper-left, upper-right, lower-left, lower-right.
        quad = vertices[index:index + 4]
        polygons.append([tuple(quad[i]) for i in (0, 1, 3, 2)])
    if not polygons:
        # Some nonconforming PDFs omit QuadPoints. The rectangle is the only
        # available selection evidence; never expand it toward nearby text.
        rect = annot.rect
        polygons = [[(rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)]]

    selections = [
        (polygon, (min(point[0] for point in polygon), min(point[1] for point in polygon),
                   max(point[0] for point in polygon), max(point[1] for point in polygon)))
        for polygon in polygons
    ]
    selected_lines: list[str] = []
    selected_blocks: set[int] = set()
    for line in page_text.lines:
        runs: list[str] = []
        current: list[str] = []
        for char in line.chars:
            x, y = char.center
            selected = any(
                bounds[0] - 0.05 <= x <= bounds[2] + 0.05
                and bounds[1] - 0.05 <= y <= bounds[3] + 0.05
                and _inside_polygon(char.center, polygon)
                for polygon, bounds in selections
            )
            if selected:
                current.append(char.text)
            elif current:
                runs.append("".join(current).strip())
                current = []
        if current:
            runs.append("".join(current).strip())
        text = " … ".join(run for run in runs if run)
        if text:
            selected_lines.append(text)
            selected_blocks.add(line.block)
    context = "\n\n".join(page_text.blocks[index].text for index in sorted(selected_blocks) if page_text.blocks[index].text)
    return "\n".join(selected_lines), context


def _nearby_context(rect: fitz.Rect, page_text: _PageText, page: fitz.Page) -> str:
    """Return the closest text block, with a distance limit for isolated notes."""
    center_x, center_y = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
    candidates = []
    # Page furniture is rarely the paragraph a margin note refers to. Keep it
    # as a fallback for pages that contain only header / footer text.
    body_blocks = [block for block in page_text.blocks if block.text and
                   block.rect.y0 >= page.cropbox.height * 0.06 and
                   block.rect.y1 <= page.cropbox.height * 0.93]
    for block in body_blocks or page_text.blocks:
        if not block.text:
            continue
        dx = max(block.rect.x0 - center_x, 0, center_x - block.rect.x1)
        dy = max(block.rect.y0 - center_y, 0, center_y - block.rect.y1)
        distance = math.hypot(dx, dy)
        # Vertical alignment is useful when note icons sit in a page margin.
        candidates.append((distance, abs((block.rect.y0 + block.rect.y1) / 2 - center_y), block))
    if not candidates:
        return ""
    distance, _, block = min(candidates, key=lambda value: (value[0], value[1]))
    if distance > max(180.0, page.cropbox.width * 0.32):
        return ""
    return block.text


def _color(annot: fitz.Annot) -> tuple[str, str]:
    colors = annot.colors
    value = colors.get("stroke") or colors.get("fill") or []
    if len(value) == 1:
        rgb = [value[0]] * 3
    elif len(value) == 3:
        rgb = value
    elif len(value) == 4:
        c, m, y, k = value
        rgb = [(1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k)]
    else:
        return "Belirsiz", "#808080"
    rgb = [min(1.0, max(0.0, float(component))) for component in rgb]
    color_hex = "#" + "".join(f"{round(component * 255):02X}" for component in rgb)
    hue, saturation, brightness = colorsys.rgb_to_hsv(*rgb)
    if brightness < 0.18:
        return "Siyah", color_hex
    if saturation < 0.06:
        return ("Beyaz" if brightness > 0.92 else "Gri"), color_hex
    degrees = hue * 360
    if degrees < 12 or degrees >= 345:
        name = "Pembe" if brightness > 0.85 and min(rgb) > 0.35 else "Kırmızı"
    elif degrees < 43:
        name = "Turuncu"
    elif degrees < 73:
        name = "Sarı"
    elif degrees < 175:
        name = "Yeşil"
    elif degrees < 198:
        name = "Turkuaz"
    elif degrees < 255:
        name = "Mavi"
    elif degrees < 291:
        name = "Mor"
    else:
        name = "Mor" if brightness < 0.75 else "Pembe"
    return name, color_hex


def _date(value: str) -> str:
    if not value:
        return ""
    match = re.fullmatch(r"(?:D:)?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(?:(Z)|([+-])(\d{2})'?((?:\d{2}))?'?)?", value)
    if not match:
        return value
    year, month, day, hour, minute, second, utc, sign, tz_hour, tz_minute = match.groups()
    try:
        tz = None
        if utc:
            tz = timezone.utc
        elif sign:
            offset = timedelta(hours=int(tz_hour), minutes=int(tz_minute or 0))
            tz = timezone(offset if sign == "+" else -offset)
        return datetime(int(year), int(month or 1), int(day or 1), int(hour or 0), int(minute or 0), int(second or 0), tzinfo=tz).isoformat()
    except (ValueError, OverflowError):
        return value


def _reply_parent(doc: fitz.Document, xref: int) -> int | None:
    # /IRT also links grouped graphical annotations. Those are independent
    # selections, not conversation replies, and must keep their own quotes.
    _, reply_type = doc.xref_get_key(xref, "RT")
    if reply_type == "/Group":
        return None
    value_type, value = doc.xref_get_key(xref, "IRT")
    if value_type == "xref":
        match = re.match(r"(\d+)\s+\d+\s+R", value)
        if match:
            return int(match.group(1))
    return None


def _reply_text(record: AnnotationRecord) -> str:
    metadata = " · ".join(value for value in (record.author, record.created or record.modified) if value)
    label = f"Yanıt ({metadata})" if metadata else "Yanıt"
    return f"{label}: {record.comment}" if record.comment else label


def extract_pdf(data: bytes, filename: str, password: str = "") -> ExtractionResult:
    """Read standards-based annotations from a PDF; no OCR is performed.

    ``quote`` is the selected markup text. ``context`` is a PDF text-block
    heuristic and ``context_inferred`` always flags that distinction. Replies
    are attached to the root annotation instead of becoming duplicate records.
    """
    if not data:
        raise PDFExtractionError("PDF dosyası boş. Geçerli bir PDF yükleyin.")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as error:
        raise PDFExtractionError("PDF açılamadı. Dosya bozuk olabilir veya geçerli bir PDF olmayabilir.") from error

    try:
        if doc.needs_pass:
            if not password:
                raise PDFExtractionError("Bu PDF parola korumalı. PDF parolasını girin.")
            if not doc.authenticate(password):
                raise PDFExtractionError("PDF parolası yanlış. Doğru parola ile yeniden deneyin.")
        if not doc.is_pdf or doc.page_count == 0:
            raise PDFExtractionError("Dosya geçerli, sayfaları olan bir PDF değil.")
        title = (doc.metadata or {}).get("title", "").strip() or Path(filename).stem
        result = ExtractionResult(filename=filename, title=title, page_count=doc.page_count)
        if doc.is_repaired:
            result.warnings.append("PDF okunurken dosya yapısı onarıldı; eksik notlar veya metinler olabilir.")
        document_id = hashlib.sha256(data + b"\0" + filename.encode("utf-8")).hexdigest()[:16]
        records: dict[int, AnnotationRecord] = {}
        parents: dict[int, int] = {}
        text_page_count = 0
        annotation_count = 0
        for page_index in range(doc.page_count):
            page_number = page_index + 1
            try:
                page = doc.load_page(page_index)
            except Exception:
                result.warnings.append(f"{page_number}. sayfa okunamadı; diğer sayfalara devam edildi.")
                continue
            try:
                page_text = _page_text(page)
            except Exception:
                page_text = _PageText([], [])
                result.warnings.append(f"{page_number}. sayfanın metin katmanı okunamadı; not açıklamaları korunmaya çalışıldı.")
            if any(block.text for block in page_text.blocks):
                text_page_count += 1
            try:
                annotation_xrefs = page.annot_xrefs()
            except Exception:
                result.warnings.append(f"{page_number}. sayfanın not listesi okunamadı; diğer sayfalara devam edildi.")
                continue
            for xref, annot_type, *_ in annotation_xrefs:
                if annot_type in {1, 16, 20, 21}:  # links, popups, widgets, screen
                    continue
                annotation_count += 1
                try:
                    annot = page.load_annot(xref)
                    if annot is None:
                        raise ValueError("Annotation unavailable")
                    info = annot.info or {}
                    comment = (info.get("content") or "").strip()
                    parent = _reply_parent(doc, xref)
                    if annot_type not in _MARKUP_TYPES and annot_type not in {0, 2, 14} and not comment and parent is None:
                        continue
                    color_name, color_hex = _color(annot)
                    quote, context = "", ""
                    if annot_type in _MARKUP_TYPES:
                        quote, context = _marked_text(annot, page_text)
                        if not quote:
                            result.warnings.append(f"{page_number}. sayfadaki bir işaretlemenin seçili metni bulunamadı. Tarama, metin katmanı veya seçim geometrisi nedeniyle açıklama tek başına aktarılmış olabilir.")
                    else:
                        context = _nearby_context(annot.rect, page_text, page)
                    record = AnnotationRecord(
                        id=f"{document_id}-p{page_number}-a{xref}",
                        filename=filename,
                        document_title=title,
                        page=page_number,
                        kind=_KINDS.get(annot_type, "Açıklama"),
                        color_name=color_name,
                        color_hex=color_hex,
                        quote=quote,
                        context=context,
                        comment=comment,
                        author=(info.get("title") or "").strip(),
                        created=_date(info.get("creationDate") or ""),
                        modified=_date(info.get("modDate") or ""),
                        rect=tuple(round(float(value), 3) for value in annot.rect),
                        context_inferred=bool(context),
                    )
                    records[xref] = record
                    if parent is not None:
                        parents[xref] = parent
                    if annot_type in {17, 18, 19}:
                        result.warnings.append(f"{page_number}. sayfadaki ekin yalnızca açıklaması aktarıldı; ek dosya veya medya içeriği aktarılmadı.")
                except Exception:
                    result.warnings.append(f"{page_number}. sayfadaki bir not okunamadı; diğer notlara devam edildi.")

        reply_records: set[int] = set()
        for xref, parent in parents.items():
            visited = {xref}
            while parent in parents and parent not in visited:
                visited.add(parent)
                parent = parents[parent]
            if parent in records and parent not in visited:
                target = records[parent]
                target.comment = "\n\n".join(value for value in (target.comment, _reply_text(records[xref])) if value)
                reply_records.add(xref)
            else:
                result.warnings.append(f"{records[xref].page}. sayfadaki bir yanıt ana nota bağlanamadı; ayrı not olarak aktarıldı.")
        result.records = [record for xref, record in records.items() if xref not in reply_records]
        if not text_page_count:
            result.warnings.append("PDF’de okunabilir metin katmanı bulunamadı. Taranmış sayfalardaki alıntıları çıkarmak için önce OCR uygulayın; bu uygulama OCR yapmaz.")
        elif text_page_count < doc.page_count:
            result.warnings.append("Bazı sayfalarda okunabilir metin katmanı yok. Bu sayfalardaki taranmış alıntılar için önce OCR uygulayın.")
        if not annotation_count:
            result.warnings.append("PDF’de standart PDF notu veya işaretleme bulunamadı. Sayfaya birleştirilmiş renkler, çizgiler ve görüntü olarak kaydedilmiş notlar ayrı açıklama olarak çıkarılamaz.")
        elif not result.records:
            result.warnings.append("Aktarılabilecek metin işaretlemesi veya açıklamalı not bulunamadı.")
        # Avoid repeated warnings from annotations with the same limitation.
        result.warnings = list(dict.fromkeys(result.warnings))
        return result
    except PDFExtractionError:
        raise
    except Exception as error:
        raise PDFExtractionError("PDF işlenemedi. Dosyanın açılabildiğini ve geçerli bir PDF olduğunu kontrol edin.") from error
    finally:
        doc.close()
