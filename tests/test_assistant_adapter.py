from pathlib import Path
import sys

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from adapters.assistant import OpenAICompatibleAssistantProvider


def test_local_http_provider_is_allowed_and_structured():
    calls = []

    def transport(url, payload, headers, timeout):
        calls.append((url, payload, headers, timeout))
        return {
            "choices": [{
                "message": {
                    "content": '{"kind":"capability_request","capabilities":["image.generate"]}'
                }
            }]
        }

    provider = OpenAICompatibleAssistantProvider(
        "http://127.0.0.1:1920",
        "tiny-intent-model",
        transport=transport,
    )
    result = provider.propose(
        "make an image",
        {"capability_ids": ["image.generate"], "graph_controls": []},
    )

    assert result["kind"] == "capability_request"
    url, payload, headers, timeout = calls[0]
    assert url == "http://127.0.0.1:1920/v1/chat/completions"
    assert payload["temperature"] == 0
    assert payload["response_format"] == {"type": "json_object"}
    assert "tools" not in payload
    assert "tool_choice" not in payload
    assert headers == {}


def test_remote_provider_requires_https_and_api_key_is_header_only():
    for bad in (
        "http://example.com",
        "ftp://example.com",
        "https://user:pass@example.com",
    ):
        try:
            OpenAICompatibleAssistantProvider(bad, "model")
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe provider URL accepted: {bad}")

    calls = []

    def transport(url, payload, headers, timeout):
        calls.append((url, payload, headers))
        return {"choices": [{"message": {"content": '{"kind":"message","message":"ok"}'}}]}

    provider = OpenAICompatibleAssistantProvider(
        "https://api.example.com",
        "model",
        api_key="secret-token",
        transport=transport,
    )
    result = provider.propose("hello", {"capability_ids": []})
    assert result["kind"] == "message"
    assert calls[0][2] == {"Authorization": "Bearer secret-token"}
    assert "secret-token" not in str(calls[0][1])


def test_provider_rejects_malformed_endpoint_response():
    provider = OpenAICompatibleAssistantProvider(
        "http://localhost:1920",
        "model",
        transport=lambda *_: {"choices": []},
    )
    try:
        provider.propose("hello", {})
    except RuntimeError as exc:
        assert "missing message content" in str(exc)
    else:
        raise AssertionError("missing content was accepted")

    provider = OpenAICompatibleAssistantProvider(
        "http://localhost:1920",
        "model",
        transport=lambda *_: {"choices": [{"message": {"content": "not-json"}}]},
    )
    try:
        provider.propose("hello", {})
    except RuntimeError as exc:
        assert "valid JSON" in str(exc)
    else:
        raise AssertionError("malformed JSON proposal was accepted")
