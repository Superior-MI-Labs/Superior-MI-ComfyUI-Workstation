from pathlib import Path
import ast
import collections

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "app" / "main.py"
SRC = MAIN.read_text()
TREE = ast.parse(SRC)

ATTACH_METHODS = {
    "add", "pack_start", "pack_end", "append_page",
    "pack1", "pack2", "attach", "add_with_viewport",
}

def _assigned_lines(fn):
    assigned = collections.defaultdict(list)
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned[target.id].append(node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned[node.target.id].append(node.lineno)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name):
            assigned[node.target.id].append(node.lineno)
    return assigned

def test_no_widget_instance_is_attached_to_two_parents():
    failures = []
    for fn in [n for n in ast.walk(TREE) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        assigned = _assigned_lines(fn)
        groups = collections.defaultdict(list)
        for node in ast.walk(fn):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in ATTACH_METHODS
                and node.args
                and isinstance(node.args[0], ast.Name)
            ):
                continue
            child = node.args[0].id
            prior = [line for line in assigned[child] if line <= node.lineno]
            epoch = max(prior) if prior else None
            parent = ast.unparse(node.func.value)
            groups[(child, epoch)].append((node.lineno, parent, node.func.attr))

        for (child, epoch), uses in groups.items():
            parents = {parent for _, parent, _ in uses}
            if len(uses) > 1 and len(parents) > 1:
                failures.append((fn.name, child, epoch, uses))

    assert not failures, f"GTK child attached to multiple parents: {failures}"

def test_starter_pack_details_scroll_container_is_the_paned_child():
    assert "right_sc.add(right)" in SRC
    assert "paned.pack2(right_sc, True, False)" in SRC
    assert "paned.pack2(right, True, False)" not in SRC

def test_library_is_nested_lazy_not_eager():
    fn = next(n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef) and n.name == "_library")
    body = ast.get_source_segment(SRC, fn)
    assert "self._lazy_notebook" in body
    assert "self.library_tabs.append_page(self._starter_packs()" not in body
    assert "self.library_tabs.append_page(self._characters()" not in body
    assert "self.library_tabs.append_page(self._picks()" not in body
