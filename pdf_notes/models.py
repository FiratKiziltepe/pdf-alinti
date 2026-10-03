"""Shared, serializable data models for the PDF annotation application."""

from dataclasses import dataclass, field


@dataclass
class AnnotationRecord:
    id: str
    filename: str
    document_title: str
    page: int
    kind: str
    color_name: str
    color_hex: str
    quote: str = ""
    context: str = ""
    comment: str = ""
    author: str = ""
    created: str = ""
    modified: str = ""
    rect: tuple[float, float, float, float] | None = None
    context_inferred: bool = False
    # PNG encoded as base64 keeps records JSON-serializable and self-contained.
    image_base64: str = ""


@dataclass
class ExtractionResult:
    filename: str
    title: str = ""
    page_count: int = 0
    records: list[AnnotationRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class PDFExtractionError(ValueError):
    """An actionable error for an unreadable or locked PDF."""
