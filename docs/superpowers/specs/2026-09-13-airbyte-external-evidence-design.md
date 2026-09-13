# AgentOps External Evidence & Connector Layer

## Status

Approved architecture; implementation follows this specification.

## Goal

Add an optional external-evidence subsystem to AgentOps Control Center so specialist agents can obtain authorized, structured context from external systems without replacing the deterministic release-policy engine.

## Architecture

AgentOps remains the authoritative control plane. External connectors are evidence providers only: they may retrieve or inspect external context, but they cannot approve releases, change release policy, or authorize destructive/external actions.

The first provider is an optional Airbyte adapter using Airbyte's agent-oriented connector SDK where practical. The provider exposes OpenAI Agents-compatible tools behind the existing deferred tool-loading model. The deterministic runtime remains the default and rollback/reference path.

## Core Components

### 1. ExternalContextProvider abstraction

Define a small provider interface with a stable AgentOps-facing contract. A provider should be able to:

- identify the provider and connector capability;
- inspect available connector capabilities without executing an external action;
- execute an explicitly authorized read/evidence operation;
- return a structured evidence envelope;
- expose provider/operation metadata suitable for audit logging.

The abstraction must not depend on Airbyte-specific classes in the core control-plane policy code.

### 2. Structured evidence envelope

Every external result must be normalized into an AgentOps evidence object containing, at minimum:

- provider;
- connector/capability identifier;
- operation name;
- status (`SUCCESS` or `FAILED`);
- evidence payload or bounded textual representation;
- source/provenance metadata when available;
- timestamp;
- retry count when applicable;
- truncation indicator when output is bounded;
- error information when execution fails.

The envelope is evidence, not a release decision.

### 3. Airbyte adapter

Implement Airbyte as an optional provider. Prefer the Airbyte Agent SDK's OpenAI Agents integration (`framework="openai_agents"`) when available. The adapter must keep Airbyte imports optional so the deterministic runtime and core application remain usable without Airbyte installed.

Use the Airbyte progressive tool model where supported:

1. inspect connector;
2. read connector skill documentation when needed;
3. execute an explicitly authorized operation.

Do not expose arbitrary external execution as a generic unrestricted tool.

### 4. Authorization boundary

External evidence access must be allowlisted. The first implementation should support provider/connector/operation-level authorization and default-deny behavior.

The external evidence layer must explicitly reject destructive or write operations unless a future policy extension enables them. The initial release supports read/evidence operations only.

Agent instructions must continue to state that specialists cannot approve releases or authorize external actions.

### 5. Output-size guard

Bound external evidence before it reaches the manager model or audit log. Preserve an explicit truncation flag and enough metadata to understand that the returned evidence was bounded.

This protects context windows and prevents large connector responses from becoming an unbounded model-input path.

### 6. Retry policy

Transient provider failures may be retried with a small bounded retry policy. Retries must be visible in the evidence envelope/audit record. Permanent authorization failures and invalid operations must not be retried.

### 7. Audit integration

External evidence access must produce structured audit events containing provider, connector, operation, authorization decision, status, retry count, and evidence/provenance metadata. Audit records must not include credentials or secrets.

### 8. OpenAI Agents integration

The existing manager/specialist architecture remains intact. External connector tools should be compatible with the existing deferred tool-search strategy rather than adding all connector schemas to the initial model request.

External evidence tools are supplemental to the seven specialist reviews. The manager continues to consolidate specialist reports, while deterministic release gates remain authoritative outside the LLM runtime.

## Safety and Scope Constraints

- `AGENT_RUNTIME=deterministic` remains the default.
- No API key is required for deterministic tests.
- Airbyte is optional; do not make the full Airbyte platform a mandatory dependency.
- Do not replace or bypass the deterministic severity gate.
- Do not add automatic release approval based on model output.
- Do not enable destructive external operations in the initial adapter.
- Do not log credentials, access tokens, or connector secrets.
- Do not couple deterministic policy evaluation to an external provider's availability.

## Testing Strategy

Tests must cover behavior at the AgentOps boundary rather than requiring live external credentials:

- provider contract and evidence-envelope normalization;
- default-deny authorization;
- read operation allowlisting;
- rejection of write/destructive operations;
- output-size bounding and truncation metadata;
- bounded transient retry behavior;
- structured audit events without secrets;
- optional Airbyte dependency behavior when the SDK is absent;
- OpenAI Agents tool-shape compatibility and deferred loading;
- deterministic release policy behavior remains unchanged.

A live Airbyte/API-key integration test is optional and must never be required for the default CI suite.

## Non-Goals

- Installing or operating the full Airbyte platform.
- Migrating AgentOps away from its deterministic runtime.
- Replacing the eight-role AgentOps model.
- Building a general-purpose arbitrary API execution engine.
- Granting agents autonomous write/delete/deploy permissions.
- Making external evidence a prerequisite for every deterministic run.

## Future Extensions

After the first provider is stable, the architecture can add:

- GitHub evidence connector;
- per-agent connector capability registry;
- stronger provenance/lineage identifiers;
- provider health monitoring;
- MCP-backed providers;
- human approval workflows for narrowly scoped external write operations.
