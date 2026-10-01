"""The small, bundled demonstration PDF works without network access or fonts."""

from pathlib import Path


def demo_pdf_bytes() -> bytes:
    """Read a two-page Turkish PDF with nine genuine PDF annotations."""
    return (Path(__file__).resolve().parent.parent / "assets" / "ornek-notlar.pdf").read_bytes()
