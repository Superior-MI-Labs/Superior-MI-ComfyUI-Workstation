from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from core.assistant import AssistantService, build_assistant_context
from core.contracts import CapabilityDefinition, GraphControl
from core.graph_controls import GraphControlRegistry
from core.registry import CapabilityRegistry


def context():
    capabilities = CapabilityRegistry((
        CapabilityDefinition(id="image.generate", title="Generate Image"),
        CapabilityDefinition(id="video.generate", title="Generate Video"),
    ))
    controls = GraphControlRegistry((
        GraphControl(
            id="1.steps",
            node_id="1",
            node_type="KSampler",
            input_name="steps",
            data_type="INT",
            value=24,
            widget="slider-number",
            label="Steps",
            group="Sampling",
            minimum=1,
            maximum=100,
            step=1,
            priority="primary",
        ),
        GraphControl(
            id="1.sampler_name",
            node_id="1",
            node_type="KSampler",
            input_name="sampler_name",
            data_type="COMBO",
            value="euler",
            widget="dropdown",
            label="Sampler",
            group="Sampling",
            choices=("euler", "dpmpp_2m"),
        ),
        GraphControl(
            id="2.opaque",
            node_id="2",
            node_type="ThirdParty",
            input_name="opaque",
            data_type="*",
            value="x",
            widget="read-only",
            label="Opaque",
            group="Advanced",
            editable=False,
        ),
    ))
    return build_assistant_context(capabilities, controls)


class Provider:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def propose(self, user_text, provider_context):
        self.calls.append((user_text, provider_context))
        return self.response


def test_assistant_off_does_not_disable_core():
    service = AssistantService(None)
    result = service.propose("make an image", context())

    assert service.available is False
    assert result.kind == "message"
    assert "not configured" in result.message
    assert not hasattr(service, "execute")
    assert not hasattr(service, "install")
    assert not hasattr(service, "download")


def test_provider_can_only_request_known_capabilities():
    provider = Provider({
        "kind": "capability_request",
        "capabilities": ["image.generate"],
        "local_only": True,
        "quality_priority": "quality",
        "storage_budget_bytes": 50_000,
        "preferences": {"style": "illustration"},
        "message": "Use the image capability.",
    })
    service = AssistantService(provider)
    result = service.propose("make an image", context())

    assert result.kind == "capability_request"
    assert result.capability_request is not None
    assert result.capability_request.capabilities == ("image.generate",)
    assert result.capability_request.quality_priority == "quality"
    assert provider.calls[0][1]["capability_ids"] == [
        "image.generate",
        "video.generate",
    ]


def test_unknown_capability_is_rejected():
    service = AssistantService(Provider({
        "kind": "capability_request",
        "capabilities": ["shell.execute"],
    }))

    try:
        service.propose("do anything", context())
    except ValueError as exc:
        assert "unknown capabilities" in str(exc)
    else:
        raise AssertionError("unknown assistant capability was accepted")


def test_graph_change_is_validated_against_registered_control():
    service = AssistantService(Provider({
        "kind": "graph_changes",
        "changes": {"1.steps": 32, "1.sampler_name": "dpmpp_2m"},
        "message": "Use 32 steps.",
    }))
    result = service.propose("use 32 steps", context())

    assert result.kind == "graph_changes"
    assert result.graph_changes == {
        "1.steps": 32,
        "1.sampler_name": "dpmpp_2m",
    }


def test_unknown_noneditable_and_out_of_range_graph_changes_fail():
    bad = (
        {"kind": "graph_changes", "changes": {"999.command": "rm"}},
        {"kind": "graph_changes", "changes": {"2.opaque": "changed"}},
        {"kind": "graph_changes", "changes": {"1.steps": 500}},
        {"kind": "graph_changes", "changes": {"1.sampler_name": "invented"}},
    )
    for proposal in bad:
        service = AssistantService(Provider(proposal))
        try:
            service.propose("change it", context())
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"unsafe graph proposal accepted: {proposal}")


def test_provider_cannot_smuggle_command_or_package_fields():
    proposals = (
        {
            "kind": "graph_changes",
            "changes": {"1.steps": 30},
            "command": "rm -rf /",
        },
        {
            "kind": "capability_request",
            "capabilities": ["image.generate"],
            "package_id": "evil",
        },
        {
            "kind": "message",
            "message": "hello",
            "url": "https://example.com/model",
        },
    )
    for proposal in proposals:
        service = AssistantService(Provider(proposal))
        try:
            service.propose("test", context())
        except ValueError as exc:
            assert "unsupported keys" in str(exc)
        else:
            raise AssertionError("provider smuggled unsupported authority")


def test_clarify_requires_a_real_message():
    service = AssistantService(Provider({"kind": "clarify", "message": "Which output do you want?"}))
    result = service.propose("make it", context())
    assert result.kind == "clarify"

    try:
        AssistantService(Provider({"kind": "clarify", "message": ""})).propose("make it", context())
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:
        raise AssertionError("empty clarification was accepted")


def test_empty_user_text_is_rejected_before_provider():
    provider = Provider({"kind": "message", "message": "unused"})
    try:
        AssistantService(provider).propose("   ", context())
    except ValueError as exc:
        assert "must not be empty" in str(exc)
    else:
        raise AssertionError("empty user text reached provider")
    assert provider.calls == []
