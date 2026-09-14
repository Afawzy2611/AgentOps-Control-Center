# External Evidence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the merged external-evidence layer so structured payloads are bounded, provenance is explicit, and audit records remain safe and useful without changing release authority.

**Architecture:** Keep `ExternalEvidence` provider-neutral and make output bounding operate on a deterministic serialized representation for both scalar and structured payloads. Preserve default-deny authorization, bounded retries, and the deterministic release gate; add only additive provenance/audit metadata needed for traceability.

**Tech Stack:** Python 3.13, dataclasses, JSON serialization, pytest, OpenAI Agents SDK integration already present.

**Spec:** `docs/superpowers/specs/2026-09-13-airbyte-external-evidence-design.md`

## Global Constraints

- Airbyte remains optional; deterministic runtime remains the default.
- External evidence is read-only and cannot approve, unblock, or alter release decisions.
- Secrets must never be persisted in audit metadata or error messages.
- Output limits apply to structured and unstructured provider payloads.
- Retries remain bounded and occur only for explicitly retryable exceptions.
- Keep changes additive; do not replace the eight AgentOps roles.

---

### Task 1: Establish regression coverage for structured output bounds

**Files:**
- Modify: `tests/test_external_evidence.py`

**Interfaces:**
- Consumes: `execute_evidence_operation`, `bounded_text`, `ExternalEvidence`.
- Produces: regression tests proving structured payloads are bounded and marked truncated.

- [ ] **Step 1: Write the failing test** for a dict/list payload whose serialized representation exceeds `max_output_chars`.
- [ ] **Step 2: Run the focused test** and verify it fails against the current string-only bounding behavior.
- [ ] **Step 3: Add a regression test** for a payload exactly at the configured limit.
- [ ] **Step 4: Run the focused tests** and verify the new tests fail only for the missing structured behavior.

### Task 2: Implement deterministic structured output bounding

**Files:**
- Modify: `app/external_evidence.py`
- Test: `tests/test_external_evidence.py`

**Interfaces:**
- Consumes: arbitrary provider payloads.
- Produces: bounded payloads plus accurate `truncated` metadata without changing provider contracts.

- [ ] **Step 1: Implement a JSON-first bounding helper** that preserves strings as strings and serializes structured values deterministically.
- [ ] **Step 2: Ensure oversized structured values are represented safely without embedding unbounded provider output.
- [ ] **Step 3: Preserve existing scalar behavior and existing retry/authorization semantics.
- [ ] **Step 4: Run focused external-evidence tests.

### Task 3: Strengthen provenance and audit semantics

**Files:**
- Modify: `app/external_evidence.py`
- Modify: `tests/test_external_evidence.py`

**Interfaces:**
- Consumes: provider/connector/operation metadata and arguments.
- Produces: provenance that identifies the provider/connector/operation while retaining secret-safe argument metadata.

- [ ] **Step 1: Add failing tests** for audit provenance containing stable operation identity and redacted argument keys.
- [ ] **Step 2: Implement additive audit provenance fields without storing argument values.
- [ ] **Step 3: Verify secret values never appear in success or failure audit records.
- [ ] **Step 4: Run focused tests.

### Task 4: Regression-check the full runtime surface and documentation

**Files:**
- Modify: `tests/test_agentops.py` only if regression coverage requires it.
- Modify: `README.md` if the hardened behavior changes the documented contract.

**Interfaces:**
- Consumes: hardened external-evidence API.
- Produces: documentation and tests consistent with the merged Agents SDK integration.

- [ ] **Step 1: Run the complete test suite with the repository's documented dependencies.
- [ ] **Step 2: Inspect the final diff for deterministic-release invariants and secret-safety regressions.
- [ ] **Step 3: Update documentation only where behavior changed.
- [ ] **Step 4: Run the complete suite again after documentation/code changes.

### Task 5: Review, commit, push, and verify

**Files:**
- All changed files from Tasks 1-4.

- [ ] **Step 1: Perform a code-review pass against the spec and plan.
- [ ] **Step 2: Create a focused commit for the hardening changes.
- [ ] **Step 3: Open a PR against `main`.
- [ ] **Step 4: Wait for CI and inspect the actual test job result.
- [ ] **Step 5: If CI passes, mark the PR ready for review; otherwise debug the failure before any merge.
- [ ] **Step 6: Merge only after fresh verification confirms the final head SHA.
