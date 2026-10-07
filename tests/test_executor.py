from pathlib import Path
import sys
import tempfile

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.contracts import ActionPlan, PlanAction
from core.executor import PlanExecutor, approval_for, fingerprint_plan
from core.journal import JsonlExecutionJournal, MemoryExecutionJournal


class FakePackageService:
    def __init__(self):
        self.calls = []

    def install(self, package_id):
        self.calls.append(package_id)
        return f"installed:{package_id}"


class FakeAssetService:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def download(self, asset_id):
        self.calls.append(asset_id)
        if self.fail:
            raise RuntimeError("simulated download failure")
        return f"downloaded:{asset_id}"




class FakeRuntimeService:
    def __init__(self):
        self.calls = []

    def prepare(self, backend):
        self.calls.append(("prepare", backend))
        return f"prepared:{backend}"

    def restart(self):
        self.calls.append(("restart", None))
        return "restarted"


class FakeWorkflowService:
    def __init__(self):
        self.calls = []

    def load_blueprint(self, blueprint_id):
        self.calls.append(("load", blueprint_id))
        return f"loaded:{blueprint_id}"

    def validate(self):
        self.calls.append(("validate", None))
        return "validated"


def setup_plan():
    return ActionPlan(
        id="setup",
        title="Setup",
        actions=(
            PlanAction(
                id="package.node",
                kind="install_package",
                title="Install node",
                requires_approval=True,
                payload={"package_id": "node.example"},
            ),
            PlanAction(
                id="asset.model",
                kind="download_asset",
                title="Download model",
                requires_approval=True,
                payload={"asset_id": "model.example", "size_bytes": 1000},
            ),
        ),
    )


def test_mutations_do_not_run_without_complete_plan_approval():
    packages = FakePackageService()
    assets = FakeAssetService()
    executor = PlanExecutor(package_service=packages, asset_service=assets)

    result = executor.execute(setup_plan())

    assert result.blocked
    assert not result.completed
    assert packages.calls == []
    assert assets.calls == []


def test_approval_is_bound_to_exact_plan_content():
    packages = FakePackageService()
    assets = FakeAssetService()
    executor = PlanExecutor(package_service=packages, asset_service=assets)
    original = setup_plan()
    approval = approval_for(original, {"package.node", "asset.model"})

    changed = ActionPlan(
        id=original.id,
        title=original.title,
        actions=(
            original.actions[0],
            PlanAction(
                id="asset.model",
                kind="download_asset",
                title="Download different model",
                requires_approval=True,
                payload={"asset_id": "model.different", "size_bytes": 1000},
            ),
        ),
    )

    result = executor.execute(changed, approval)

    assert result.blocked
    assert "does not match" in result.actions[0].message
    assert packages.calls == []
    assert assets.calls == []


def test_fully_approved_plan_dispatches_only_registered_actions():
    packages = FakePackageService()
    assets = FakeAssetService()
    executor = PlanExecutor(package_service=packages, asset_service=assets)
    plan = setup_plan()
    approval = approval_for(plan, {"package.node", "asset.model"})

    result = executor.execute(plan, approval)

    assert result.completed
    assert [row.status for row in result.actions] == ["complete", "complete"]
    assert packages.calls == ["node.example"]
    assert assets.calls == ["model.example"]


def test_plan_schema_is_validated_before_any_side_effect():
    packages = FakePackageService()
    executor = PlanExecutor(package_service=packages)

    bad = ActionPlan(
        id="bad",
        title="Bad",
        actions=(
            PlanAction(
                id="package.node",
                kind="install_package",
                title="Install",
                payload={"package_id": "node.example", "command": "rm -rf /"},
            ),
        ),
    )

    try:
        executor.execute(bad)
    except ValueError as exc:
        assert "unsupported payload keys" in str(exc)
    else:
        raise AssertionError("unsupported payload reached executor")
    assert packages.calls == []


def test_unknown_action_kind_is_rejected_before_execution():
    packages = FakePackageService()
    executor = PlanExecutor(package_service=packages)
    bad = ActionPlan(
        id="bad",
        title="Bad",
        actions=(
            PlanAction(id="x", kind="shell", title="No", payload={"command": "anything"}),
        ),
    )
    try:
        executor.execute(bad)
    except ValueError as exc:
        assert "Unsupported action kind" in str(exc)
    else:
        raise AssertionError("unknown action kind was accepted")
    assert packages.calls == []


def test_retry_skips_completed_action_and_resumes_after_failure():
    journal = MemoryExecutionJournal()
    packages = FakePackageService()
    broken_assets = FakeAssetService(fail=True)
    plan = setup_plan()
    approval = approval_for(plan, {"package.node", "asset.model"})

    first = PlanExecutor(
        journal=journal,
        package_service=packages,
        asset_service=broken_assets,
    ).execute(plan, approval)

    assert [row.status for row in first.actions] == ["complete", "failed"]
    assert packages.calls == ["node.example"]
    assert broken_assets.calls == ["model.example"]

    fixed_assets = FakeAssetService()
    second = PlanExecutor(
        journal=journal,
        package_service=packages,
        asset_service=fixed_assets,
    ).execute(plan, approval)

    assert [row.status for row in second.actions] == ["skipped", "complete"]
    assert packages.calls == ["node.example"]
    assert fixed_assets.calls == ["model.example"]
    assert second.completed


def test_failure_blocks_later_actions_in_same_attempt():
    assets = FakeAssetService(fail=True)
    workflows = FakeWorkflowService()
    plan = ActionPlan(
        id="failure-order",
        title="Failure",
        actions=(
            PlanAction(
                id="asset",
                kind="download_asset",
                title="Download",
                payload={"asset_id": "model.example"},
            ),
            PlanAction(
                id="validate",
                kind="validate_workflow",
                title="Validate",
            ),
        ),
    )

    result = PlanExecutor(
        asset_service=assets,
        workflow_service=workflows,
    ).execute(plan)

    assert [row.status for row in result.actions] == ["failed", "blocked"]
    assert workflows.calls == []


def test_jsonl_journal_survives_process_reconstruction():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "journal.jsonl"
        first_journal = JsonlExecutionJournal(path)
        packages = FakePackageService()
        plan = ActionPlan(
            id="one",
            title="One",
            actions=(
                PlanAction(
                    id="package",
                    kind="install_package",
                    title="Install",
                    payload={"package_id": "node.example"},
                ),
            ),
        )
        first = PlanExecutor(
            journal=first_journal,
            package_service=packages,
        ).execute(plan)
        assert first.completed

        second_journal = JsonlExecutionJournal(path)
        second = PlanExecutor(
            journal=second_journal,
            package_service=packages,
        ).execute(plan)

        assert second.actions[0].status == "skipped"
        assert packages.calls == ["node.example"]


def test_plan_fingerprint_is_stable_for_same_content():
    assert fingerprint_plan(setup_plan()) == fingerprint_plan(setup_plan())



def test_runtime_restart_is_a_registered_explicit_action():
    runtime = FakeRuntimeService()
    plan = ActionPlan(
        id="runtime",
        title="Runtime",
        actions=(
            PlanAction(
                id="prepare",
                kind="prepare_runtime",
                title="Prepare CUDA",
                requires_approval=True,
                payload={"backend": "cuda"},
            ),
            PlanAction(
                id="restart",
                kind="restart_runtime",
                title="Restart",
            ),
        ),
    )
    approval = approval_for(plan, {"prepare"})
    result = PlanExecutor(runtime_service=runtime).execute(plan, approval)

    assert result.completed
    assert runtime.calls == [("prepare", "cuda"), ("restart", None)]
