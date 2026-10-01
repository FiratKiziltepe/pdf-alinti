"""Exercise the user workflow through Streamlit's real script runner."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


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
