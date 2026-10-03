"""Exercise the user workflow through Streamlit's real script runner."""

from pathlib import Path

from streamlit.testing.v1 import AppTest
import fitz

from pdf_notes.extract import extract_pdf


APP = Path(__file__).resolve().parents[1] / "app.py"


def button(app, label):
    return next(item for item in app.button if item.label == label)


def load_demo():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    button(app, "Örnek PDF ile dene").click().run()
    assert not app.exception
    return app


def test_demo_filter_export_preview_and_clear():
    app = load_demo()
    assert [metric.value for metric in app.metric][:2] == ["1", "9"]
    assert len(app.session_state["results"][0].records) == 9
    app.text_input(key="pdf_password_0").set_value("private-test-password").run()
    app.multiselect(key="filter_colors").set_value(["Sarı"]).run()
    assert not app.exception
    cards = [item.value for item in app.markdown if 'class="quote-card"' in item.value]
    assert len(cards) == 2
    assert all("Sarı" in card for card in cards)
    app.selectbox(key="export_format").select("Excel (.xlsx)").run()
    assert not app.exception
    assert any(key[1] == "xlsx" for key in app.session_state["export_cache"])
    button(app, "Sayfa önizlemesini aç").click().run()
    assert not app.exception
    assert next(iter(app.session_state["preview_cache"].values())).startswith(b"\x89PNG")
    button(app, "Oturumu temizle").click().run()
    assert not app.exception
    assert "results" not in app.session_state
    assert not app.metric
    assert "sources" not in app.session_state
    assert app.text_input(key="pdf_password_1").value == ""
    assert "pdf_password_0" not in app.session_state


def test_turkish_search_and_no_results():
    app = load_demo()
    app.text_input(key="search").set_value("TEK BİR ÖRNEK").run()
    assert not app.exception
    cards = [item.value for item in app.markdown if 'class="quote-card"' in item.value]
    assert len(cards) == 2
    app.text_input(key="search").set_value("qzx_not_found_987").run()
    assert not app.exception
    assert not [item for item in app.markdown if 'class="quote-card"' in item.value]
    assert any("kayıt bulunamadı" in item.value for item in app.info)
    assert button(app, "İndirilecek kayıt yok").disabled


def test_visual_note_card_filter_and_exports():
    with fitz.open() as doc:
        page = doc.new_page()
        page.add_rect_annot(fitz.Rect(60, 60, 200, 200))
        data = doc.tobytes()
    result = extract_pdf(data, "table.pdf")
    app = AppTest.from_file(str(APP), default_timeout=30)
    app.session_state["results"] = [result]
    app.session_state["sources"] = {"table.pdf": {"data": data, "password": ""}}
    app.session_state["export_cache"] = {}
    app.session_state["preview_cache"] = {}
    app.run()
    assert not app.exception
    card, = [item.value for item in app.markdown if 'class="quote-card"' in item.value]
    assert "data:image/png;base64," in card
    assert "ÇERÇEVE İÇİNDEKİ ALAN" in card
    app.multiselect(key="filter_kinds").set_value(["Görsel not (çerçeve)"]).run()
    assert not app.exception
    app.selectbox(key="export_format").select("Excel (.xlsx)").run()
    assert not app.exception
    assert any(key[1] == "xlsx" for key in app.session_state["export_cache"])
    app.selectbox(key="export_format").select("CSV (.csv)").run()
    assert any("CSV yalnızca metin" in item.value for item in app.caption)


def test_pdf_download_context_switch_uses_distinct_cached_exports():
    app = load_demo()
    app.selectbox(key="export_format").select("PDF (.pdf)").run()
    assert not app.exception
    cards = [item.value for item in app.markdown if 'class="quote-card"' in item.value]
    assert any("Sizin notunuz" in card and "Bağlam" in card and "Alıntı" in card for card in cards)
    assert any(key[1:] == ("pdf", True) for key in app.session_state["export_cache"])
    app.checkbox(key="export_context").uncheck().run()
    assert not app.exception
    exports = app.session_state["export_cache"]
    with_context = next(value for key, value in exports.items() if key[1:] == ("pdf", True))
    without_context = next(value for key, value in exports.items() if key[1:] == ("pdf", False))
    with fitz.open(stream=with_context, filetype="pdf") as pdf:
        assert "Bağlam" in "".join(page.get_text() for page in pdf)
    with fitz.open(stream=without_context, filetype="pdf") as pdf:
        text = "".join(page.get_text() for page in pdf)
        assert "Bağlam" not in text
        assert "Sizin notunuz" in text
    assert app.checkbox(key="show_context").value is True
