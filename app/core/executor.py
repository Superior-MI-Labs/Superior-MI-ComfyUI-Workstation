from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Mapping, Protocol

from .contracts import (
    ActionExecution,
    ActionPlan,
    PlanAction,
    PlanApproval,
    PlanExecutionResult,
)
from .journal import ExecutionJournal, MemoryExecutionJournal


class PackageService(Protocol):
    def install(self, package_id: str) -> str: ...


class AssetService(Protocol):
    def download(self, asset_id: str) -> str: ...


class RuntimeService(Protocol):
    def prepare(self, backend: str) -> str: ...
    def restart(self) -> str: ...


class WorkflowService(Protocol):
    def load_blueprint(self, blueprint_id: str) -> str: ...
    def validate(self) -> str: ...


_ACTION_PAYLOADS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "inspect_hardware": (frozenset(), frozenset()),
    "inspect_runtime": (frozenset(), frozenset()),
    "review_license": (
        frozenset({"candidate_id", "license_status"}),
        frozenset({"candidate_id", "license_status"}),
    ),
    "prepare_runtime": (frozenset({"backend"}), frozenset({"backend"})),
    "restart_runtime": (frozenset(), frozenset()),
    "install_package": (frozenset({"package_id"}), frozenset({"package_id"})),
    "download_asset": (
        frozenset({"asset_id"}),
        frozenset({"asset_id", "size_bytes"}),
    ),
    "load_blueprint": (frozenset({"blueprint_id"}), frozenset({"blueprint_id"})),
    "validate_workflow": (frozenset(), frozenset()),
}


def _jsonable_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    try:
        encoded = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("Plan action payload must be JSON-serializable data.") from exc


def fingerprint_action(action: PlanAction) -> str:
    payload = {
        "id": action.id,
        "kind": action.kind,
        "title": action.title,
        "requires_approval": action.requires_approval,
        "payload": _jsonable_payload(action.payload),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def fingerprint_plan(plan: ActionPlan) -> str:
    payload = {
        "id": plan.id,
        "title": plan.title,
        "summary": plan.summary,
        "actions": [
            {
                "fingerprint": fingerprint_action(action),
                "status": action.status,
            }
            for action in plan.actions
        ],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_plan_for_execution(plan: ActionPlan) -> None:
    ids = [action.id for action in plan.actions]
    if len(ids) != len(set(ids)):
        raise ValueError("Action IDs must be unique within an ActionPlan.")

    for action in plan.actions:
        schema = _ACTION_PAYLOADS.get(action.kind)
        if schema is None:
            raise ValueError(f"Unsupported action kind: {action.kind}")
        required, allowed = schema
        payload = _jsonable_payload(action.payload)
        keys = frozenset(payload)
        missing = required - keys
        extra = keys - allowed
        if missing:
            raise ValueError(f"Action {action.id} is missing required payload keys: {sorted(missing)}")
        if extra:
            raise ValueError(f"Action {action.id} has unsupported payload keys: {sorted(extra)}")


def approval_for(plan: ActionPlan, action_ids: set[str] | frozenset[str]) -> PlanApproval:
    """Bind approval to the exact immutable plan content shown to the user."""
    return PlanApproval(
        plan_fingerprint=fingerprint_plan(plan),
        action_ids=frozenset(action_ids),
    )


class PlanExecutor:
    def __init__(
        self,
        *,
        journal: ExecutionJournal | None = None,
        package_service: PackageService | None = None,
        asset_service: AssetService | None = None,
        runtime_service: RuntimeService | None = None,
        workflow_service: WorkflowService | None = None,
    ):
        self.journal = journal or MemoryExecutionJournal()
        self.package_service = package_service
        self.asset_service = asset_service
        self.runtime_service = runtime_service
        self.workflow_service = workflow_service

    def _approval_block(
        self,
        plan: ActionPlan,
        plan_fingerprint: str,
        message: str,
    ) -> PlanExecutionResult:
        return PlanExecutionResult(
            plan_id=plan.id,
            plan_fingerprint=plan_fingerprint,
            actions=tuple(
                ActionExecution(action_id=action.id, status="blocked", message=message)
                for action in plan.actions
            ),
            completed=False,
        )

    def execute(
        self,
        plan: ActionPlan,
        approval: PlanApproval | None = None,
    ) -> PlanExecutionResult:
        # Validate the whole plan before any side effect is possible.
        validate_plan_for_execution(plan)
        plan_fingerprint = fingerprint_plan(plan)

        required_approvals = {
            action.id for action in plan.actions if action.requires_approval
        }
        if required_approvals:
            if approval is None:
                return self._approval_block(
                    plan,
                    plan_fingerprint,
                    "Plan contains actions that require explicit approval.",
                )
            if approval.plan_fingerprint != plan_fingerprint:
                return self._approval_block(
                    plan,
                    plan_fingerprint,
                    "Approval does not match the current plan.",
                )
            missing = required_approvals - set(approval.action_ids)
            if missing:
                return self._approval_block(
                    plan,
                    plan_fingerprint,
                    "Missing approval for: " + ", ".join(sorted(missing)),
                )

        outcomes: list[ActionExecution] = []
        failed = False

        for action in plan.actions:
            if failed:
                outcomes.append(
                    ActionExecution(
                        action_id=action.id,
                        status="blocked",
                        message="Not run because an earlier action failed.",
                    )
                )
                continue

            action_fingerprint = fingerprint_action(action)
            if self.journal.is_complete(action_fingerprint):
                outcomes.append(
                    ActionExecution(
                        action_id=action.id,
                        status="skipped",
                        message="Already completed with the same action fingerprint.",
                    )
                )
                continue

            try:
                message = self._execute_action(action)
            except Exception as exc:
                outcomes.append(
                    ActionExecution(
                        action_id=action.id,
                        status="failed",
                        message=str(exc),
                    )
                )
                failed = True
                continue

            self.journal.record_complete(
                action_fingerprint,
                action.id,
                message,
            )
            outcomes.append(
                ActionExecution(
                    action_id=action.id,
                    status="complete",
                    message=message,
                )
            )

        completed = bool(outcomes) and all(
            outcome.status in {"complete", "skipped"} for outcome in outcomes
        )
        if not plan.actions:
            completed = True

        return PlanExecutionResult(
            plan_id=plan.id,
            plan_fingerprint=plan_fingerprint,
            actions=tuple(outcomes),
            completed=completed,
        )

    def _execute_action(self, action: PlanAction) -> str:
        payload = dict(action.payload)

        if action.kind == "inspect_hardware":
            return "Hardware inspection already represented by the qualified plan."
        if action.kind == "inspect_runtime":
            return "Runtime inspection already represented by the qualified plan."
        if action.kind == "review_license":
            # Reaching this handler means the exact approval-bound plan passed
            # the preflight approval gate.
            return f"Terms acknowledged for {payload['candidate_id']}."
        if action.kind == "prepare_runtime":
            if self.runtime_service is None:
                raise RuntimeError("No RuntimeService is configured.")
            return self.runtime_service.prepare(str(payload["backend"]))
        if action.kind == "restart_runtime":
            if self.runtime_service is None:
                raise RuntimeError("No RuntimeService is configured.")
            return self.runtime_service.restart()
        if action.kind == "install_package":
            if self.package_service is None:
                raise RuntimeError("No PackageService is configured.")
            return self.package_service.install(str(payload["package_id"]))
        if action.kind == "download_asset":
            if self.asset_service is None:
                raise RuntimeError("No AssetService is configured.")
            return self.asset_service.download(str(payload["asset_id"]))
        if action.kind == "load_blueprint":
            if self.workflow_service is None:
                raise RuntimeError("No WorkflowService is configured.")
            return self.workflow_service.load_blueprint(str(payload["blueprint_id"]))
        if action.kind == "validate_workflow":
            if self.workflow_service is None:
                raise RuntimeError("No WorkflowService is configured.")
            return self.workflow_service.validate()

        # validate_plan_for_execution should make this unreachable.
        raise RuntimeError(f"No executor for action kind: {action.kind}")
