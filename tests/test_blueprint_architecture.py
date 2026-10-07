import json
import tempfile
from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

import blueprint_manager
import comfy_integration

def test_packs_have_stacks():
    packs=blueprint_manager.load_packs()
    assert len(packs)>=4
    assert all(p.get("stack_ids") for p in packs)

def test_blueprints_are_derived_from_one_manifest():
    rows=blueprint_manager.load_blueprints()
    assert len(rows)>=40
    assert any(x.family=="Qwen Image 2.1" for x in rows)
    assert any(x.family=="Wan2.2 TI2V 5B" for x in rows)
    assert all(x.stack_id for x in rows)
    assert all(x.capability_id for x in rows)
    assert not any(x.category == "Character" for x in rows)
    assert any(x.category == "Reference" for x in rows)


def test_blueprint_manager_has_no_family_stack_or_character_flag_authority():
    source=(APP / "blueprint_manager.py").read_text()
    assert "FAMILY_STACK" not in source
    assert "character_aware" not in source
    assert 'entry.get("stack_id"' in source
    assert 'entry.get("capability_id"' in source

def test_api_prompt_to_ui_graph():
    prompt={
      "1":{"class_type":"LoadA","inputs":{"name":"model.bin"},"_meta":{"title":"Loader"}},
      "2":{"class_type":"UseA","inputs":{"model":["1",0],"steps":4},"_meta":{"title":"Use"}},
    }
    info={
      "LoadA":{"input":{"required":{"name":["STRING",{}]}},"output":["MODEL"],"output_name":["MODEL"]},
      "UseA":{"input":{"required":{"model":["MODEL",{}],"steps":["INT",{}]}},"output":["IMAGE"],"output_name":["IMAGE"]},
    }
    ui=comfy_integration.api_prompt_to_ui(prompt,info)
    assert ui["version"]==0.4
    assert len(ui["nodes"])==2
    assert len(ui["links"])==1
    assert ui["nodes"][1]["inputs"][0]["link"]==1
