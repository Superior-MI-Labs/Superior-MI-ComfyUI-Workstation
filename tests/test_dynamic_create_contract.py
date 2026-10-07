from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_ROOT = ROOT / "bridge" / "Superior-MI-Workstation-Bridge" / "web" / "js"
MAIN = JS_ROOT / "superior-mi-workstation.js"
CONTROLS = JS_ROOT / "smi-graph-controls.js"


def test_create_uses_live_comfy_graph_not_a_second_value_store():
    source = MAIN.read_text(encoding="utf-8")
    assert "deriveGraphControls(app.graph)" in source
    assert "readLiveControlValue(app.graph, control)" in source
    assert "writeLiveControlValue(" in source
    assert "app.graph" in source
    assert "app.canvas?.setDirty?.(true, true)" in source


def test_create_projects_primary_and_advanced_controls_from_same_graph():
    source = MAIN.read_text(encoding="utf-8")
    assert 'control.priority === "primary" || showAdvanced' in source
    assert '"Show advanced"' in source
    assert '"Hide advanced"' in source


def test_graph_control_writer_uses_native_widget_callback_and_graph_change():
    source = CONTROLS.read_text(encoding="utf-8")
    assert "live.widget.value = value" in source
    assert "live.widget.callback?.(value)" in source
    assert "live.node.graph?.change?.()" in source


def test_unknown_widgets_fail_closed():
    source = CONTROLS.read_text(encoding="utf-8")
    assert 'return "unsupported"' in source
    assert 'kind !== "unsupported" && kind !== "file"' in source
    assert "Graph control is not editable" in source


def test_character_domain_does_not_reenter_core_create_surface():
    combined = (
        MAIN.read_text(encoding="utf-8")
        + "\n"
        + CONTROLS.read_text(encoding="utf-8")
    ).lower()
    assert "character studio" not in combined
    assert "character_aware" not in combined
    assert "canonical character" not in combined
