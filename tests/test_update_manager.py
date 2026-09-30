from pathlib import Path
import sys
APP=Path(__file__).resolve().parents[1]/"app"
sys.path.insert(0,str(APP))
import update_manager

def test_version_compare():
    assert update_manager.is_newer("3.1.0","3.0.1")
    assert not update_manager.is_newer("3.0.1","3.0.1")
    assert not update_manager.is_newer("3.0.0","3.0.1")

def test_update_url_namespace_guard():
    assert update_manager._allowed_update_url("https://github.com/Superior-MI-Labs/repo/releases/download/v/x.deb")
    assert not update_manager._allowed_update_url("https://example.com/x.deb")
