from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "bridge" / "Superior-MI-Workstation-Bridge"
JS = BRIDGE / "web" / "js" / "superior-mi-workstation.js"
PY = BRIDGE / "__init__.py"


def test_bridge_uses_native_comfy_sidebar_and_real_graph():
    source = JS.read_text(encoding="utf-8")
    assert "registerSidebarTab" in source
    assert "superior-mi-workstation" in source
    assert "app.loadGraphData" in source
    assert 'title: "Superior MI"' in source


def test_studio_does_not_embed_or_reimplement_a_graph_editor():
    source = JS.read_text(encoding="utf-8").lower()
    forbidden = (
        "<iframe",
        "createelement(\"iframe\")",
        "new lgraphcanvas",
        "new lgraph(",
        "litegraph.create",
    )
    assert not any(token in source for token in forbidden)


def test_core_sidebar_is_domain_neutral():
    source = JS.read_text(encoding="utf-8").lower()
    assert "character studio" not in source
    assert "canonical character" not in source
    assert 'const sections = ["home", "create", "activity", "system"]' in source


def test_bridge_retains_backend_workflow_handoff_routes():
    source = PY.read_text(encoding="utf-8")
    assert 'WEB_DIRECTORY = "./web/js"' in source
    assert '"/superior-mi/open-workflow"' in source
    assert '"/superior-mi/pending-workflow"' in source
    assert '"/superior-mi/bridge/status"' in source
    assert '"version": "2"' in source
