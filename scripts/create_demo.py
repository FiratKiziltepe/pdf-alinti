"""Regenerate the synthetic Turkish academic-reading example.

Run ``python scripts/create_demo.py`` from the project directory. PyMuPDF is
the only dependency. The checked-in PDF already embeds its font; font discovery
is needed only when regenerating it. An explicit font can be supplied with
``--font /path/to/DejaVuSans.ttf``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf


INK = (0.13, 0.19, 0.24)
MUTED = (0.37, 0.44, 0.48)
TEAL = (0.06, 0.40, 0.38)
PAPER = (0.985, 0.983, 0.965)
FONT_NAME = "demo_sans"
FONT_SIZE = 10.8
ANNOTATION_DATE = "D:20261001093000+00'00'"


def locate_font(explicit: Path | None = None) -> Path:
    candidates = [explicit] if explicit else [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/local/share/fonts/DejaVuSans.ttf"),
        Path.home() / ".fonts" / "DejaVuSans.ttf",
        Path("/Library/Fonts/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Türkçe karakterleri destekleyen bir TTF bulunamadı. "
        "--font /yol/DejaVuSans.ttf ile bir yazı tipi belirtin. "
        "Hazır assets/ornek-notlar.pdf dosyası yazı tipi gerektirmez."
    )


def write_box(page: pymupdf.Page, rect: tuple[float, float, float, float], text: str,
              fontsize: float = FONT_SIZE, color: tuple = INK) -> None:
    result = page.insert_textbox(
        pymupdf.Rect(rect), text, fontname=FONT_NAME, fontsize=fontsize,
        lineheight=1.55 if fontsize <= 13 else 1.25, color=color,
    )
    if result < 0:
        raise RuntimeError(f"Text did not fit: {text[:70]!r}")


def decorate_page(page: pymupdf.Page, font: Path, number: int) -> None:
    page.insert_font(fontname=FONT_NAME, fontfile=str(font))
    page.draw_rect(page.rect, color=None, fill=PAPER)
    page.draw_rect(pymupdf.Rect(0, 0, 595, 10), color=None, fill=TEAL)
    write_box(page, (55, 36, 540, 59), "OKUMA ATÖLYESİ  /  SENTETİK ÖRNEK", 9, TEAL)
    page.draw_line(pymupdf.Point(55, 777), pymupdf.Point(540, 777), color=(.79, .83, .80), width=.6)
    write_box(page, (55, 790, 490, 822),
              "Gösterim için üretilmiştir. Gerçek bir makale veya kaynak değildir.", 8, MUTED)
    write_box(page, (516, 790, 540, 822), f"{number:02d}", 9, TEAL)


def annotate(page: pymupdf.Page, phrase: str, kind: str, color: tuple,
             comment: str, author: str = "Deniz Araştırmacı") -> pymupdf.Annot:
    quads = page.search_for(phrase, quads=True)
    if not quads:
        raise RuntimeError(f"Annotation target absent: {phrase!r}")
    add = {
        "Highlight": page.add_highlight_annot,
        "Underline": page.add_underline_annot,
        "Squiggly": page.add_squiggly_annot,
        "StrikeOut": page.add_strikeout_annot,
    }[kind]
    annotation = add(quads)
    annotation.set_colors(stroke=color)
    annotation.set_opacity(.48 if kind == "Highlight" else .9)
    annotation.set_info(
        title=author, subject=f"Araştırma notu · {kind}", content=comment,
        creationDate=ANNOTATION_DATE, modDate=ANNOTATION_DATE,
    )
    annotation.update()
    return annotation


def create_demo(font: Path) -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    decorate_page(page, font, 1)
    write_box(page, (55, 80, 540, 153), "Akademik okumada\nrenkler ve araştırma notları", 23)
    write_box(page, (55, 169, 540, 214),
              "Örnek çalışma metni  •  Sürüm 1  •  1 Ekim 2026", 9, MUTED)
    write_box(page, (55, 220, 540, 244), "01  Renkler bir düşünme aracıdır", 13, TEAL)
    write_box(page, (55, 255, 540, 355),
              "Okuma sırasında verilen renkler, düşünceleri görünür kılar. "
              "Sarı işaretler yazıda kullanılabilecek temel savları; yeşil işaretler "
              "yöntem ve uygulama önerilerini temsil edebilir. Bu renkler evrensel "
              "bir standart değildir: her araştırmacı kendi çalışma düzenine göre "
              "anlam atar. Bu örnekte sarı, doğrudan alıntı adayı olarak kullanılır.")
    write_box(page, (55, 384, 540, 408), "02  Yöntem ile yorumu birlikte saklamak", 13, TEAL)
    write_box(page, (55, 419, 540, 514),
              "Bir alıntı, kaynağın bağlamı ile birlikte saklanmalıdır. "
              "Sayfa numarası, işaret rengi ve okuyucunun açıklaması aynı kayıtta "
              "bir araya geldiğinde yazım sırasında kaynak takibi kolaylaşır. "
              "Okuyucunun yorumu ile metindeki ifade ayrı alanlarda tutulur; "
              "böylece özgün sözler ve çalışma notları açık biçimde ayırt edilir.")
    write_box(page, (55, 553, 540, 577), "03  Eleştirel okuma ve sınırlar", 13, TEAL)
    write_box(page, (55, 588, 540, 687),
              "Tek bir örnek, genel bir sonuca ulaşmak için yeterli değildir. "
              "Kırmızı işaretler karşılaştırılması gereken iddiaları veya "
              "araştırma sorularını görünür kılabilir. Bir okuyucu bu paragrafın "
              "yanına örneklem çeşitliliğiyle ilgili bir not ekleyebilir. Notun "
              "yakınındaki paragraf, yorumun anlaşılması için yararlı bir bağlamdır.")
    annotate(page, "Okuma sırasında verilen renkler, düşünceleri görünür kılar.",
             "Highlight", (1, .82, .13),
             "Girişte renk kodlamanın amacı için alıntı adayı. Kendi renk sözlüğümü yöntem bölümünde açıklayacağım.")
    annotate(page, "Bir alıntı, kaynağın bağlamı ile birlikte saklanmalıdır.",
             "Highlight", (.30, .80, .45),
             "Uygulama önerisi: alıntıyla sayfa, renk ve açıklamayı aynı tabloda dışa aktar.")
    annotate(page, "Tek bir örnek, genel bir sonuca ulaşmak için yeterli değildir.",
             "Highlight", (1, .35, .35),
             "Sınırlılık başlığı için önemli. Tekil örneklerin genellenmesi hakkında ek kaynak ara.")
    sticky = page.add_text_annot(pymupdf.Point(31, 627),
                                 "Bu paragrafı örneklem çeşitliliği tartışmasıyla ilişkilendir. "
                                 "Karşılaştırmalı bir çalışma eklemek gerekli.", icon="Comment")
    sticky.set_info(title="Deniz Araştırmacı", subject="Paragraf açıklaması",
                    creationDate=ANNOTATION_DATE, modDate=ANNOTATION_DATE)
    sticky.set_colors(stroke=(1, .82, .13))
    sticky.update()

    page = doc.new_page(width=595, height=842)
    decorate_page(page, font, 2)
    write_box(page, (55, 80, 540, 124), "Alıntıdan yazım taslağına", 23)
    write_box(page, (55, 142, 540, 167), "04  İlişkileri kurmak", 13, TEAL)
    write_box(page, (55, 181, 540, 281),
              "Okuma notları, farklı metinler arasında bağlantı kurmaya yardımcı olur. "
              "Mavi işaretler kavramsal tanımları veya başka kaynaklarla kurulacak "
              "ilişkileri gösterebilir. Dışa aktarılan kayıtların kaynak dosyası ve "
              "sayfası korunursa, bir cümleyi yeniden kontrol etmek kolaylaşır. "
              "Bu deneme metni herhangi bir bilimsel bulgu bildirmez.")
    write_box(page, (55, 315, 540, 340), "05  Alt çizgiler ve soru işaretleri", 13, TEAL)
    write_box(page, (55, 354, 540, 450),
              "Doğrudan alıntı yapılırken özgün ifade korunmalıdır. "
              "Altı çizili bölüm, yazım sırasında özellikle hatırlanacak bir "
              "ilkeyi temsil eder. Dalgalı çizgi ise bir ifadenin açıklığa "
              "kavuşturulması gerektiğini hatırlatabilir. Renk ile işaret türü "
              "aynı şeyi anlatmaz; ikisi ayrı bilgiler olarak kaydedilir.")
    write_box(page, (55, 488, 540, 513), "06  Bir varsayımı gözden geçirmek", 13, TEAL)
    write_box(page, (55, 527, 540, 613),
              "Bütün PDF dosyaları seçilebilir metin içerir. "
              "Bu varsayım doğru değildir: taranmış sayfalarda metin görüntü "
              "olarak bulunabilir. Üzeri çizilen ilk cümle, eleştirilen "
              "varsayımı gösterir. Böyle bir durumda yorum dışa aktarılabilir; "
              "alıntı metnini çıkarmak ise OCR gerektirebilir.")
    annotate(page, "Okuma notları, farklı metinler arasında bağlantı kurmaya yardımcı olur.",
             "Highlight", (.27, .61, 1),
             "Kavramsal bağ: notları temalara göre gruplamak, makalenin tartışma taslağını hazırlayabilir.")
    annotate(page, "Doğrudan alıntı yapılırken özgün ifade korunmalıdır.",
             "Underline", (.24, .47, .81),
             "Yazım kontrolü: alıntı metnini kaynak sayfasıyla karşılaştır.")
    annotate(page, "Renk ile işaret türü aynı şeyi anlatmaz;", "Squiggly", (.89, .41, .12),
             "Bu ayrımı yöntem notlarında somut bir örnekle açıklamak yararlı olur.")
    annotate(page, "Bütün PDF dosyaları seçilebilir metin içerir.", "StrikeOut", (.91, .23, .23),
             "Yanlış varsayım. Taranmış PDF'lerde ayrıca OCR gerekir; uygulama bunu açıkça belirtmeli.")
    freetext_content = (
        "Yazım notu: Alıntıları sayfa numarasıyla birlikte kullan. "
        "Araştırmacının açıklamasını özgün cümleden ayrı tut."
    )
    freetext = page.add_freetext_annot(
        pymupdf.Rect(55, 654, 540, 724),
        freetext_content,
        fontsize=10, fill_color=(.89, .95, .93), text_color=INK,
        border_color=(.61, .78, .72), border_width=1, richtext=True,
        style="font-family: sans-serif; font-size: 10pt; color: #21303d; text-indent: 0;",
    )
    freetext.set_info(title="Deniz Araştırmacı", subject="Serbest metin notu",
                     content=freetext_content,
                     creationDate=ANNOTATION_DATE, modDate=ANNOTATION_DATE)
    doc.set_metadata({
        "title": "Akademik okumada renkler ve araştırma notları — Sentetik örnek",
        "author": "PDF Alıntı uygulaması · Örnek belge",
        "subject": "İki sayfalık sentetik Türkçe metin ve gerçek PDF açıklamaları",
        "keywords": "sentetik, örnek, araştırma, highlight, alt çizgi, PDF notu",
        "creator": "PDF Alıntı · create_demo.py",
        "creationDate": ANNOTATION_DATE,
        "modDate": ANNOTATION_DATE,
    })
    doc.subset_fonts()
    data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parent.parent / "assets" / "ornek-notlar.pdf")
    args = parser.parse_args()
    data = create_demo(locate_font(args.font))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        assert len(doc) == 2
        assert sum(1 for p in doc for _ in p.annots()) == 9
        assert "özgün ifade korunmalıdır" in " ".join(p.get_text() for p in doc)
    print(f"Örnek PDF: {args.output} ({len(data):,} bayt, 2 sayfa, 9 açıklama)")


if __name__ == "__main__":
    main()
