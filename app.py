"""A Turkish Streamlit workspace for exporting PDF quotes and annotations."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata

import streamlit as st

from pdf_notes.demo import demo_pdf_bytes
from pdf_notes.exporters import (
    export_csv,
    export_docx,
    export_json,
    export_markdown,
    export_xlsx,
)
from pdf_notes.extract import extract_pdf
from pdf_notes.models import AnnotationRecord, PDFExtractionError
from pdf_notes.preview import render_page


st.set_page_config(page_title="Alıntı · PDF not defteri", page_icon="📑", layout="wide")

MAX_FILES = 10
MAX_FILE_BYTES = 50 * 1024 * 1024
PAGE_SIZE = 15
EXPORT_FORMATS = {
    "Word (.docx)": (export_docx, "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "Excel (.xlsx)": (export_xlsx, "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "Markdown (.md)": (export_markdown, "md", "text/markdown; charset=utf-8"),
    "CSV (.csv)": (export_csv, "csv", "text/csv; charset=utf-8"),
    "JSON (.json)": (export_json, "json", "application/json"),
}


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def searchable(value: str) -> str:
    # Match Turkish capital I/İ and lowercase ı/i as the user expects.
    value = value.replace("İ", "i").replace("I", "ı").lower().replace("ı", "i")
    return "".join(c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c))


def reset_workspace() -> None:
    for key in list(st.session_state):
        if key not in {"uploader_version"}:
            del st.session_state[key]
    st.session_state.uploader_version += 1


def process_documents(inputs: list[tuple[str, bytes]], password: str = "") -> None:
    results, sources, errors = [], {}, []
    names: set[str] = set()
    for original_name, data in inputs:
        # Keep source labels unambiguous even when uploads have the same name.
        filename = original_name
        index = 2
        while filename in names:
            stem, _, extension = original_name.rpartition(".")
            filename = f"{stem or original_name} ({index}).{extension or 'pdf'}"
            index += 1
        names.add(filename)
        if len(data) > MAX_FILE_BYTES:
            errors.append(f"{filename}: Dosya 50 MB sınırını aşıyor.")
            continue
        try:
            result = extract_pdf(data, filename, password)
        except PDFExtractionError as error:
            errors.append(f"{filename}: {error}")
            continue
        except Exception:
            errors.append(f"{filename}: PDF işlenemedi. Dosyayı PDF okuyucunuzdan yeniden kaydedip deneyin.")
            continue
        results.append(result)
        sources[filename] = {"data": data, "password": password}
    for key in ("filter_files", "filter_colors", "filter_kinds", "filter_notes", "search", "listing_page", "preview_choice"):
        st.session_state.pop(key, None)
    st.session_state.results = results
    st.session_state.sources = sources
    st.session_state.processing_errors = errors
    st.session_state.export_cache = {}
    st.session_state.preview_cache = {}


def quotation_card(record: AnnotationRecord, show_context: bool) -> None:
    color = record.color_hex if re.fullmatch(r"#[0-9a-fA-F]{6}", record.color_hex) else "#A7AEA8"
    meta = f"{escape(record.filename)} <span>·</span> s. {record.page}"
    author = f'<span>·</span> {escape(record.author)}' if record.author else ""
    title = f'<div class="source-title">{escape(record.document_title)}</div>' if record.document_title else ""
    quotation = (
        f'<blockquote>{escape(record.quote).replace(chr(10), "<br>")}</blockquote>'
        if record.quote
        else '<div class="no-quote">Bu notun seçili bir metin aralığı yok.</div>'
    )
    note = (
        f'<div class="note"><div class="eyebrow">NOTUNUZ</div>{escape(record.comment).replace(chr(10), "<br>")}</div>'
        if record.comment else ""
    )
    context = ""
    if show_context and record.context and record.context != record.quote:
        label = "İLGİLİ PARAGRAF · KONUMDAN TAHMİN" if record.context_inferred else "PARAGRAF BAĞLAMI"
        context = f'<details class="context"><summary>{label}</summary><p>{escape(record.context).replace(chr(10), "<br>")}</p></details>'
    st.markdown(
        f'<article class="quote-card" style="--annotation-color:{color}">'
        f'<div class="card-head"><div class="source">{meta}{author}</div>'
        f'<div class="type-badge"><i style="background:{color}"></i>{escape(record.color_name)} · {escape(record.kind)}</div></div>'
        f'{title}{quotation}{note}{context}</article>',
        unsafe_allow_html=True,
    )


st.markdown("""
<style>
.block-container {max-width:1370px;padding-top:2.1rem;padding-bottom:3rem}
header[data-testid="stHeader"] {background:transparent}
[data-testid="stSidebar"] {border-right:1px solid #E2E5DB}
[data-testid="stSidebar"] .block-container {padding-top:2rem}
.brand {display:flex;align-items:center;gap:12px;font-size:29px;font-weight:700;letter-spacing:-1.2px;margin-bottom:4px}
.brand-icon {background:#30705C;color:white;width:38px;height:42px;display:inline-flex;align-items:center;justify-content:center;border-radius:9px;font-size:23px;letter-spacing:0}
.brand-note {color:#7A867E;font-size:12px;letter-spacing:1.8px;margin:0 0 2rem 50px}
.workspace-label {font-size:11px;font-weight:650;letter-spacing:1.6px;color:#788C7E;margin-bottom:10px}
.hero h1 {font-size:40px;letter-spacing:-1.5px;font-weight:650;margin:0 0 10px;line-height:1.18;color:#223A2D}
.hero p {color:#717F75;font-size:15px;line-height:1.7;max-width:720px;margin:0 0 1.5rem}
.privacy {display:inline-flex;align-items:center;gap:8px;border:1px solid #DDE7DA;background:#F2F6EE;padding:7px 11px;font-size:11px;border-radius:20px;color:#4D6B52;margin-top:12px}
.empty-panel {background:#F3F3EC;border:1px solid #E4E5DB;border-radius:14px;padding:30px 32px;margin:20px 0 18px}
.empty-panel h2 {font-size:22px;letter-spacing:-.6px;margin:0 0 12px}
.empty-panel p {font-size:14px;color:#728074;line-height:1.75;margin:0;max-width:650px}
.color-line {display:flex;gap:7px;margin-bottom:24px}.color-line i {width:32px;height:7px;border-radius:4px}
.step {border-top:1px solid #DFE4D9;padding-top:17px;margin-top:15px}
.step span {font-size:12px;color:#859681}.step h3 {font-size:16px;font-weight:600;margin:8px 0}.step p {font-size:13px;color:#748071;line-height:1.7}
.quote-card {background:white;border:1px solid #E2E7DF;border-left:4px solid var(--annotation-color);border-radius:9px;padding:20px 23px;margin:0 0 14px;box-shadow:0 2px 3px #24382903}
.card-head {display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:12px}
.source {font-size:12px;color:#647467;word-break:break-word}.source span {padding:0 7px;color:#A3ADA2}
.source-title {font-size:11px;color:#909A8C;margin-bottom:10px}
.type-badge {font-size:10px;color:#6B786A;background:#F5F6F0;padding:4px 8px;border-radius:4px;white-space:nowrap}
.type-badge i {display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}
.quote-card blockquote {border:0;padding:0;margin:0;font-family:Georgia,'Times New Roman',serif;font-size:18px;line-height:1.7;color:#293C2C;overflow-wrap:anywhere;white-space:pre-wrap}
.quote-card .note {margin-top:16px;padding:13px 15px;background:#F6F7F2;border-radius:6px;font-size:13px;color:#64705D;line-height:1.65;overflow-wrap:anywhere}
.eyebrow {font-size:9px;letter-spacing:1.6px;font-weight:700;color:#859477;margin-bottom:5px}
.context {margin-top:16px;color:#7D8975;font-size:11px}.context summary {cursor:pointer;font-size:10px;letter-spacing:.7px}.context p {line-height:1.75;font-size:13px;margin-top:12px;overflow-wrap:anywhere}
.no-quote {color:#87907F;font-size:13px;font-style:italic}
.section-title {font-size:22px;letter-spacing:-.7px;font-weight:650;margin-top:8px}
.section-note {color:#85907F;font-size:12px;margin:5px 0 20px}
.export-panel {padding:18px 20px;background:#EEF2E8;border:1px solid #DDE5D7;border-radius:9px;margin-bottom:16px}.export-panel h3 {font-size:17px;margin:0 0 7px;font-weight:600}.export-panel p {font-size:12px;color:#788770;line-height:1.7;margin:0}
[data-testid="stMetric"] {border:1px solid #E4E8DE;background:#FFF;border-radius:9px;padding:14px 17px}
[data-testid="stMetricLabel"] {color:#7D8B76;font-size:12px}
[data-testid="stMetricValue"] {font-size:26px;color:#2E4735}
div[data-testid="stFileUploader"] section {border-radius:9px}
.footer-note {color:#95A08C;font-size:11px;border-top:1px solid #E4E7DC;padding-top:14px;margin-top:25px;line-height:1.8}
@media(max-width:700px) {.block-container {padding:1rem}.hero h1 {font-size:31px}.quote-card {padding:16px}.card-head {gap:6px}.quote-card blockquote {font-size:17px}}
</style>
""", unsafe_allow_html=True)

if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0
results = st.session_state.get("results", [])
all_records = [record for result in results for record in result.records]

with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-icon">❞</span> alıntı</div><div class="brand-note">PDF NOT DEFTERİ</div>', unsafe_allow_html=True)
    st.caption("BELGELERİNİZ")
    with st.form("upload_form", clear_on_submit=False):
        uploaded = st.file_uploader(
            "PDF dosyaları yükleyin", type=["pdf"], accept_multiple_files=True,
            key=f"uploads_{st.session_state.uploader_version}",
            help="Bir seferde en fazla 10 PDF; dosya başına 50 MB.",
        )
        password = st.text_input("PDF parolası (varsa)", type="password", key=f"pdf_password_{st.session_state.uploader_version}", help="Farklı parolalı belgeleri ayrı ayrı yükleyin.")
        submitted = st.form_submit_button("Alıntıları çıkar", type="primary", width="stretch")
    if submitted:
        if not uploaded:
            st.warning("Önce en az bir PDF seçin.")
        elif len(uploaded) > MAX_FILES:
            st.error("Bir seferde en fazla 10 PDF yükleyebilirsiniz.")
        else:
            with st.spinner("PDF açıklamaları okunuyor…"):
                process_documents([(file.name, file.getvalue()) for file in uploaded], password)
            st.rerun()
    if not results:
        if st.button("Örnek PDF ile dene", width="stretch"):
            with st.spinner("Örnek notlar hazırlanıyor…"):
                process_documents([("ornek-notlar.pdf", demo_pdf_bytes())])
            st.rerun()
    st.markdown('<div class="privacy">◉ PDF’ler yalnızca bu oturumda işlenir</div>', unsafe_allow_html=True)
    st.caption("Dosyalar çalışan Streamlit sunucusunda bellekte işlenir. Kalıcı olarak kaydedilmez.")

    if results:
        st.divider()
        st.caption("GÖRÜNÜMÜ FİLTRELE")
        selected_files = st.multiselect("Belgeler", [result.filename for result in results], key="filter_files", placeholder="Tüm belgeler")
        selected_colors = st.multiselect("Renkler", sorted({record.color_name for record in all_records}), key="filter_colors", placeholder="Tüm renkler")
        selected_kinds = st.multiselect("İşaret türleri", sorted({record.kind for record in all_records}), key="filter_kinds", placeholder="Tüm işaretler")
        only_comments = st.checkbox("Yalnızca not eklenmiş olanlar", key="filter_notes")
        show_context = st.checkbox("İlgili paragrafı göster", value=True, key="show_context")
        st.divider()
        if st.button("Oturumu temizle", width="stretch"):
            reset_workspace()
            st.rerun()
        st.caption("Paragraf eşleşmesi konuma dayalıdır. Alıntıları kaynak PDF’den kontrol edebilirsiniz.")
    else:
        selected_files, selected_colors, selected_kinds, only_comments, show_context = [], [], [], False, True

st.markdown('<div class="workspace-label">ARAŞTIRMA MASANIZ</div><div class="hero"><h1>Okuduklarınız, bir arada.</h1><p>PDF’lerde işaretlediğiniz cümleleri ve kenar notlarınızı toplayın.<br>Renkleriyle düzenleyin, kaynaklarıyla birlikte makalenize taşıyın.</p></div>', unsafe_allow_html=True)

for error in st.session_state.get("processing_errors", []):
    st.error(error)
if results:
    warnings = [(result.filename, warning) for result in results for warning in result.warnings]
    if warnings:
        with st.expander(f"Belge okuma bilgisi ({len(warnings)})"):
            for filename, warning in warnings:
                st.warning(f"{filename}: {warning}")

if not results:
    st.markdown('<div class="empty-panel"><div class="color-line"><i style="background:#F3D973"></i><i style="background:#DE9A8A"></i><i style="background:#9BBB88"></i><i style="background:#91B9CC"></i></div><h2>Bir PDF yükleyerek başlayın</h2><p>Sarı bir vurgu, altı çizili bir cümle ya da bir paragrafın yanına eklediğiniz not… Hepsi tek bir not defterinde, sayfa numarası ve kaynak dosyasıyla yerini bulur.</p></div>', unsafe_allow_html=True)
    columns = st.columns(3, gap="large")
    for column, number, heading, description in zip(columns, ("01", "02", "03"), ("Belgelerinizi ekleyin", "Alıntılarınızı düzenleyin", "Yazınıza taşıyın"), ("Açıklamalarınızı PDF okuyucunuzda kaydedin; sonra soldan dosyalarınızı yükleyin.", "Renge, belgeye veya işaret türüne göre filtreleyin. Alıntıyı, notu ve paragrafı birlikte inceleyin.", "Seçtiğiniz kayıtları Word, Excel, Markdown, CSV veya JSON olarak indirin.")):
        with column:
            st.markdown(f'<div class="step"><span>{number}</span><h3>{heading}</h3><p>{description}</p></div>', unsafe_allow_html=True)
    st.markdown('<div class="footer-note">Vurgular, alt çizgiler, dalgalı çizgiler, üstü çizili metinler ve PDF notları desteklenir. Taranmış sayfalar için OCR gerekir; görüntüye dönüştürülmüş işaretler PDF açıklaması olarak okunamaz.</div>', unsafe_allow_html=True)
    st.stop()

metrics = st.columns(4)
metrics[0].metric("PDF belgesi", len(results))
metrics[1].metric("Çıkarılan kayıt", len(all_records))
metrics[2].metric("Not içeren kayıt", sum(bool(record.comment.strip()) for record in all_records))
metrics[3].metric("İşaret rengi", len({record.color_name for record in all_records}))
st.write("")

query = st.text_input("Alıntılarda ve notlarda ara", placeholder="Bir kelime, araştırma konusu veya not…", key="search")
needle = searchable(query.strip())
filtered = [
    record for record in all_records
    if (not selected_files or record.filename in selected_files)
    and (not selected_colors or record.color_name in selected_colors)
    and (not selected_kinds or record.kind in selected_kinds)
    and (not only_comments or record.comment.strip())
    and (not needle or needle in searchable(" ".join((record.quote, record.comment, record.context, record.filename, record.document_title, record.author))))
]

left, right = st.columns([2.3, 1], gap="large")
with left:
    st.markdown('<div class="section-title">Alıntılar & notlar</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-note">{len(all_records)} kayıttan {len(filtered)} tanesi gösteriliyor · Kaynak sayfa numaraları korunur</div>', unsafe_allow_html=True)
    if not filtered:
        if all_records:
            st.info("Bu filtrelere uyan kayıt bulunamadı. Filtreleri veya arama kelimesini değiştirin.")
        else:
            st.info("PDF’lerde okunabilir açıklama bulunamadı. Vurgu ve notları PDF okuyucunuzda kaydedip yeniden yükleyin.")
    else:
        page_count = (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE
        page_index = 1
        if page_count > 1:
            if st.session_state.get("listing_page", 1) > page_count:
                st.session_state.listing_page = 1
            page_index = st.number_input("Kayıt listesi sayfası", min_value=1, max_value=page_count, step=1, key="listing_page")
            st.caption(f"{page_count} liste sayfası · Her sayfada en fazla {PAGE_SIZE} kayıt")
        for record in filtered[(page_index - 1) * PAGE_SIZE:page_index * PAGE_SIZE]:
            quotation_card(record, show_context)

with right:
    st.markdown('<div class="export-panel"><h3>Makalenize taşıyın</h3><p>Geçerli filtrelere uyan tüm kayıtlar; alıntı, not, paragraf bağlamı, renk, kaynak ve sayfa bilgisiyle dışa aktarılır.</p></div>', unsafe_allow_html=True)
    chosen_format = st.selectbox("Dosya biçimi", list(EXPORT_FORMATS), key="export_format")
    export_function, extension, mime = EXPORT_FORMATS[chosen_format]
    if filtered:
        signature = hashlib.sha256("\0".join(record.id for record in filtered).encode()).hexdigest()
        cache_key = (signature, extension)
        export_cache = st.session_state.export_cache
        if cache_key not in export_cache:
            # Bound per-session memory while keeping reruns fast.
            if len(export_cache) >= 5:
                export_cache.clear()
            try:
                export_cache[cache_key] = export_function(filtered)
            except Exception:
                st.error("Dışa aktarma dosyası oluşturulamadı. Başka bir biçim seçip deneyin.")
        if cache_key in export_cache:
            st.download_button(f"{len(filtered)} kaydı indir", data=export_cache[cache_key], file_name=f"pdf-alintilar.{extension}", mime=mime, type="primary", width="stretch", key="download_records")
    else:
        st.button("İndirilecek kayıt yok", disabled=True, width="stretch")
    st.caption("Sayfa numarası PDF’nin fiziksel sayfasıdır. Dosya başlığı bibliyografik künye yerine geçmez.")

    st.divider()
    st.markdown("**Kaynak PDF’yi kontrol edin**")
    preview_options = list(dict.fromkeys((record.filename, record.page) for record in filtered))
    if preview_options:
        if st.session_state.get("preview_choice") not in preview_options:
            st.session_state.pop("preview_choice", None)
        chosen_page = st.selectbox("Belge ve sayfa", preview_options, format_func=lambda choice: f"{choice[0]} · s. {choice[1]}", key="preview_choice")
        with st.expander("İşaretli sayfayı göster", expanded=False):
            # Explicit rendering keeps large PDF workspaces responsive.
            if st.button("Sayfa önizlemesini aç", width="stretch"):
                source = st.session_state.sources[chosen_page[0]]
                try:
                    with st.spinner("Sayfa hazırlanıyor…"):
                        image = render_page(source["data"], chosen_page[1], source["password"])
                    st.session_state.preview_cache = {chosen_page: image}
                except PDFExtractionError as error:
                    st.warning(str(error))
            if chosen_page in st.session_state.preview_cache:
                st.image(st.session_state.preview_cache[chosen_page], caption=f"{chosen_page[0]} · Sayfa {chosen_page[1]}", width="stretch")
    else:
        st.caption("Önizleme için en az bir kayıt gerekli.")
    with st.expander("Hangi notlar okunabilir?"):
        st.write("PDF açıklaması olarak kaydedilen vurgular, altı çizili ve üstü çizili metinler, dalgalı çizgiler, yapışkan notlar ve metin kutuları okunur. Vurguya eklenen yorum alıntıyla birlikte korunur.")
        st.write("Bağlam alanı PDF’deki metin bloklarından konuma göre eşleştirilir; her blok tam bir paragraf olmayabilir. Sayfa önizlemesiyle kontrol edebilirsiniz.")
        st.write("Taranmış belgelerde OCR metin katmanı gerekir. Resme dönüştürülmüş veya PDF’ye kaydedilmemiş işaretler okunamaz. OCR işlemi bu sürüme dahil değildir.")
    st.download_button("Örnek açıklamalı PDF’yi indir", data=demo_pdf_bytes(), file_name="ornek-notlar.pdf", mime="application/pdf", width="stretch")

st.markdown('<div class="footer-note">Alıntı · PDF not defteri &nbsp; / &nbsp; Seçili metin kaynak alıntısıdır; not alanı PDF’ye eklenen yorumdur. İlgili paragraf konuma dayalı bir eşleştirmedir.</div>', unsafe_allow_html=True)
