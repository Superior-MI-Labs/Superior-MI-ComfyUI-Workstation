# Conversational Assistant Contract

Status: Core R1 Prompt 7

## Role

The Workstation assistant is an intent interpreter and explanation surface.

It is not:

- the package resolver;
- the package installer;
- the model downloader;
- the graph executor;
- a shell;
- a source of package or model identity.

Core remains usable without an assistant provider.

## Provider boundary

The current adapter accepts OpenAI-compatible chat-completions endpoints.

Supported deployment shapes include:

- a small local model on loopback;
- a configured remote HTTPS compatible API.

A base URL may be supplied either at its service root or at an existing
`/v1` root.

Remote plain HTTP is rejected. Credentials belong in headers and may not be
embedded in the endpoint URL.

The provider is not given tool definitions.

## Proposal vocabulary

A provider may return only one of these proposal kinds:

### capability_request

Names one or more exact semantic capability IDs already present in the
CapabilityRegistry.

The provider may express:

- local-only preference;
- quality priority;
- storage budget;
- bounded scalar preferences.

It may not name a package or model URL.

### graph_changes

Names exact editable GraphControl IDs from the current context and proposes new
values.

Core revalidates every value against type, range, choices, and editability.

### clarify

Asks one concise question when the user's goal cannot safely be mapped to known
capabilities or controls.

### message

Returns non-mutating information.

## Authority path

```text
natural language
      |
      v
optional model provider
      |
      v
untrusted JSON proposal
      |
      v
Core proposal validator
      |
      +-- CapabilityRequest -> deterministic resolver -> ActionPlan
      |
      '-- graph changes -> GraphControl validation -> graph write path
```

The provider has no path directly to PlanExecutor.

## Local tiny-model direction

A specialized model is not required initially.

The task is narrow enough for a small general instruct model with a strict
schema and current capability/control context. The deterministic validator is
the safety/correctness boundary.

If future evidence shows recurring intent-classification errors that prompting,
retrieval, or a smaller deterministic parser cannot solve, a fine-tuned intent
model may be justified later. It should still emit the same typed proposal
contract.

## Remote/free API direction

Remote compatible APIs may be offered as an opt-in provider. The Workstation
must not assume an external service is free, permanent, private, or available.

Provider configuration is therefore separate from Core capability truth.

## Security invariants

- no arbitrary commands;
- no provider-supplied package IDs;
- no provider-supplied model URLs;
- no provider-supplied action kinds;
- no direct mutation;
- no approval bypass;
- unknown capabilities fail;
- unknown or non-editable graph controls fail;
- extra proposal fields fail;
- malformed provider output fails.
