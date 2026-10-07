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
    assert '"version": "3"' in source



def test_bridge_exposes_planning_but_no_browser_execution_authority():
    backend = PY.read_text(encoding="utf-8")
    frontend = JS.read_text(encoding="utf-8")

    assert '"/superior-mi/core/status"' in backend
    assert '"/superior-mi/assistant/propose"' in backend
    assert '"/superior-mi/plan"' in backend
    assert "_is_local_request" in backend

    forbidden_backend_routes = (
        "/superior-mi/execute",
        "/superior-mi/install",
        "/superior-mi/download",
    )
    assert not any(route in backend for route in forbidden_backend_routes)

    assert '"/superior-mi/assistant/propose"' in frontend
    assert '"/superior-mi/plan"' in frontend
    assert "deriveGraphControls(app.graph)" in frontend
    assert "writeLiveControlValue(" in frontend
    assert "Apply selected changes" in frontend
    assert "Build setup checklist" in frontend


def test_home_is_not_placeholder_copy_anymore():
    source = JS.read_text(encoding="utf-8")
    assert "function renderHomePanel" in source
    assert "Ask Workstation" in source
    assert "Assistant provider" in source
    assert "will live here" not in source
