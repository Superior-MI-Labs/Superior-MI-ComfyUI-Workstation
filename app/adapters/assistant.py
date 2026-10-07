from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping


Transport = Callable[[str, Mapping[str, Any], Mapping[str, str], float], Mapping[str, Any]]


def _default_transport(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    timeout: float,
) -> Mapping[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Superior-MI-Labs-ComfyUI-Workstation",
            **dict(headers),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("Assistant endpoint returned a non-object response.")
    return result


def _validate_base_url(base_url: str) -> str:
    parsed = urllib.parse.urlsplit(str(base_url).rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Assistant base URL must be HTTP(S).")
    if parsed.username or parsed.password:
        raise ValueError("Assistant base URL must not contain embedded credentials.")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Remote assistant endpoints must use HTTPS.")
    return urllib.parse.urlunsplit(parsed).rstrip("/")


_SYSTEM_PROMPT = """You are the intent interpreter for Superior MI Workstation.

Return exactly one JSON object. You do not have tools and you cannot execute
commands, install software, download models, or mutate ComfyUI.

Allowed proposal kinds:

1. capability_request
{
  "kind": "capability_request",
  "capabilities": ["one or more exact capability_ids from context"],
  "local_only": true,
  "quality_priority": "balanced|quality|speed|storage",
  "storage_budget_bytes": null,
  "preferences": {},
  "message": "brief explanation"
}

2. graph_changes
{
  "kind": "graph_changes",
  "changes": {"exact graph control id from context": "new value"},
  "message": "brief explanation"
}

3. clarify
{
  "kind": "clarify",
  "message": "one concise question"
}

4. message
{
  "kind": "message",
  "message": "concise informational response"
}

Never invent capability IDs, graph-control IDs, package IDs, URLs, commands, or
additional keys. If the user's request cannot be expressed by the supplied
capabilities/controls, return clarify or message.
"""


def _chat_completions_url(base_url: str) -> str:
    return (
        base_url + "/chat/completions"
        if urllib.parse.urlsplit(base_url).path.rstrip("/").endswith("/v1")
        else base_url + "/v1/chat/completions"
    )


class OpenAICompatibleAssistantProvider:
    """Optional structured-intent provider for local or remote compatible APIs."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str = "",
        timeout: float = 30.0,
        transport: Transport = _default_transport,
    ):
        self.base_url = _validate_base_url(base_url)
        self.model = str(model).strip()
        if not self.model:
            raise ValueError("Assistant model is required.")
        self.api_key = str(api_key)
        self.timeout = float(timeout)
        if self.timeout <= 0:
            raise ValueError("Assistant timeout must be positive.")
        self._transport = transport

    def propose(self, user_text: str, context: Mapping[str, Any]) -> Mapping[str, Any]:
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "request": str(user_text),
                            "context": context,
                        },
                        sort_keys=True,
                        ensure_ascii=True,
                    ),
                },
            ],
        }
        response = self._transport(
            _chat_completions_url(self.base_url),
            payload,
            headers,
            self.timeout,
        )

        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Assistant endpoint response is missing message content.") from exc

        if isinstance(content, Mapping):
            proposal = dict(content)
        elif isinstance(content, str):
            try:
                proposal = json.loads(content)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Assistant endpoint did not return valid JSON content.") from exc
        else:
            raise RuntimeError("Assistant endpoint returned unsupported message content.")

        if not isinstance(proposal, dict):
            raise RuntimeError("Assistant proposal must be a JSON object.")
        return proposal
