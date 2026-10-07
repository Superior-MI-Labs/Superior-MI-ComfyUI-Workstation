# Workstation Core R1 Prompt 7 Checkpoint

Date: 2026-10-06  
Branch: `architecture/workstation-core-r1`  
Qualified source head: `18a46e38cc26b772e9aa14b4732e1aef9400fb01`

## Scope

Prompt 7 establishes a provider-independent conversational proposal layer.

The assistant is optional and has no mutation authority.

Implemented:

- `AssistantContext`;
- `AssistantProposal`;
- provider-independent `AssistantService`;
- assistant-off behavior that leaves Core operational;
- constrained proposal kinds:
  - capability_request;
  - graph_changes;
  - clarify;
  - message;
- exact CapabilityRegistry validation;
- exact GraphControl identity/type/range/choice/editability validation;
- unknown/extra proposal fields rejected;
- scalar-only bounded preference values;
- local/remote OpenAI-compatible provider adapter;
- root or `/v1` compatible endpoint handling;
- local loopback HTTP allowed;
- remote endpoints require HTTPS;
- embedded endpoint credentials rejected;
- API key carried in Authorization header only;
- JSON-object response mode;
- no tool definitions or tool-choice authority supplied to the provider.

## Authority path

```text
user language
   |
optional provider
   |
untrusted structured proposal
   |
Core validation
   |
   +-- CapabilityRequest -> deterministic resolver -> ActionPlan
   |
   '-- graph changes -> GraphControl validation -> existing graph write path
```

There is no AssistantService method for execute, install, download, or shell.

## Provider policy

A specialized model is not required initially.

A small local instruct model may serve the intent contract when configured.
A remote compatible API may be offered as an opt-in alternative.

Neither provider is treated as capability truth, package truth, model truth,
planner authority, or executor authority.

The Workstation remains usable when no AI provider is configured.

## Qualification

GitHub Actions run: 37552384161

- Python 3.11: PASS
- Python 3.12: PASS
- JavaScript graph-control test: PASS
- JavaScript syntax checks: PASS
- JSON validation: 46 files PASS
- Python test suite: 92 passed

Qualification includes:

- assistant-off operation;
- known capability proposal;
- unknown capability rejection;
- valid graph-change proposal;
- unknown graph-control rejection;
- non-editable control rejection;
- range/choice validation;
- command/package/URL field smuggling rejection;
- clarification validation;
- empty request rejection before provider call;
- local compatible endpoint;
- HTTPS-only remote endpoint;
- header-only API credentials;
- root and /v1 base URL normalization;
- malformed provider response failure.

## Next gate

Prompt 8: destructive ownership cleanup.

Delete or demote legacy ownership only where R1 replacements now exist.

Primary targets:

- Character as a Core domain;
- hard-coded `FAMILY_STACK`;
- direct-git custom-node installation as normal package authority;
- duplicate hardware/runtime setup ownership;
- old API-prompt-as-primary-graph claims and paths;
- GTK features that duplicate the native Studio/Create ownership.

Characterization tests must precede each destructive removal.
