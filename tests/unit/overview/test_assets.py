from importlib.resources import files


def _asset(name):
    return (files("schematika.overview") / "assets" / name).read_text(encoding="utf-8")


def test_cytoscape_vendored_and_nonempty():
    js = _asset("cytoscape.min.js")
    assert "cytoscape" in js.lower()
    assert len(js) > 100_000


def test_app_js_has_no_dead_v1_and_is_data_driven():
    app = _asset("app.js")
    assert "runV1" not in app
    assert 'devClass.get(dev) === "JB"' not in app
    assert "data.config" in app or "cfg" in app


def test_template_has_marker_tags():
    t = _asset("template.html")
    for tag in ("CDN_TAG", "APP_TAG", "TITLE_TAG", "VERLABEL_TAG"):
        assert tag in t
