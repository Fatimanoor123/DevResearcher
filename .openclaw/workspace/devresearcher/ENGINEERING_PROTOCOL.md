# DevResearcher Engineering Protocol

This protocol defines a safe, maintainable, and reproducible software-
engineering workflow for Python, AI/ML systems, APIs, and production services.

## 1. Standard Engineering Lifecycle

Use this lifecycle for substantial engineering work:

**UNDERSTAND → INSPECT → PLAN → IMPLEMENT → TEST → VERIFY → DOCUMENT → REPORT**

Explicitly identify stages that were skipped, unavailable, or only partially
completed.

### Understand

- Identify the user's goal, acceptance criteria, constraints, and scope.
- Clarify inputs, outputs, interfaces, compatibility requirements, and risks.
- Separate confirmed requirements from assumptions.

### Inspect

Before modifying anything, inspect the relevant files, project structure,
entry points, dependencies, configuration, tests, logs, and repository status.
Understand existing behavior and preserve unrelated user changes.

### Plan

Define the smallest safe change, affected files, implementation approach,
dependencies, risks, rollback considerations, and verification method.

### Implement

Make focused, maintainable changes within the approved scope. Preserve existing
architecture and conventions unless a justified change is required. Avoid
unrelated refactoring, unnecessary dependencies, and broad rewrites.

### Test

Run focused automated tests first, followed by broader checks appropriate to the
risk. Include normal, boundary, error, and regression cases where practical.

### Verify

Inspect the resulting state and confirm that acceptance criteria are met. Use
runtime checks, integration checks, manual inspection, or deployment checks as
appropriate. A partial test must never be presented as proof of full-system
correctness.

### Document

Update relevant usage, configuration, API, operational, and troubleshooting
documentation. Record assumptions, limitations, commands, versions, and
reproducibility details.

### Report

Report what changed, files affected, tests and checks run, exact results,
limitations, and remaining risks. State failures and unavailable checks
explicitly.

## 2. Python Development

- Inspect the supported Python version, package manager, project layout, and
  existing style before coding.
- Prefer small modules with clear interfaces, type hints where useful,
  validation, useful exceptions, and deterministic behavior where practical.
- Follow the project's formatter, linter, type-checker, and test conventions.
- Avoid mutable global state, hidden side effects, duplicated logic, and broad
  exception handling that conceals failures.
- Keep application logic separate from CLI, configuration, I/O, and framework
  integration where practical.
- Use dependency injection or explicit interfaces when it improves testing and
  maintainability.
- Add tests for normal behavior, boundary conditions, invalid inputs, and
  regressions.

## 3. AI/ML Engineering

- Record dataset, model, preprocessing, feature, prompt, evaluation, and
  environment versions.
- Prevent train/test leakage and ensure preprocessing is fit only on permitted
  data.
- Keep baselines, splits, metrics, seeds, hyperparameters, and compute budgets
  comparable and documented.
- Separate model-development experiments from production inference behavior.
- Validate inputs, handle malformed or adversarial data, and define failure and
  fallback behavior.
- Preserve experiment configurations, logs, artifacts, and reproducibility
  metadata.
- Never claim an experiment, benchmark, model evaluation, or output was run
  unless it was actually executed and observed.

## 4. API Engineering

- Inspect existing routes, schemas, authentication, middleware, versioning, and
  error conventions before changing an API.
- Define request and response schemas, status codes, validation rules, timeout
  behavior, pagination, idempotency, and compatibility expectations.
- Validate and normalize untrusted input at the boundary.
- Return stable, documented error structures without leaking secrets or
  internal implementation details.
- Apply authentication, authorization, rate limiting, logging, and input-size
  controls appropriate to the endpoint.
- Add contract, integration, and regression tests for changed behavior.
- Treat breaking changes as requiring explicit approval and a migration plan.

## 5. Debugging Protocol

Use this sequence:

**REPRODUCE → ISOLATE → IDENTIFY ROOT CAUSE → FIX → TEST → VERIFY → DOCUMENT**

### Reproduce

Capture the error, inputs, environment, command, logs, expected behavior, and
actual behavior. Reproduce locally or in the smallest representative
environment when possible.

### Isolate

Reduce the failing case, identify the smallest affected component, and compare
working and failing conditions. Inspect recent changes, dependencies,
configuration, data, and external services.

### Identify Root Cause

Form explicit hypotheses and test them with evidence. Distinguish a confirmed
root cause from a plausible explanation. Do not stop at a symptom or workaround
unless the user explicitly requests only a workaround.

### Fix

Apply the smallest safe fix that addresses the root cause. Preserve the failing
case as a regression test when practical.

### Test

Run the regression test, relevant unit or integration tests, and checks for
nearby behavior and failure modes.

### Verify

Confirm the original failure is resolved in the relevant environment and that
the fix did not introduce regressions. Report if full reproduction was not
possible.

### Document

Record the symptom, root cause, fix, commands, versions, test results, and
remaining limitations.

## 6. Testing Strategy

- Use unit tests for isolated logic and boundary conditions.
- Use integration tests for databases, filesystems, queues, model services,
  external APIs, and component boundaries.
- Use contract tests for API schemas and compatibility.
- Use end-to-end tests for critical user workflows.
- Use static analysis, formatting, linting, type checking, security scanning,
  and dependency auditing when available.
- Prefer deterministic tests with isolated fixtures and explicit cleanup.
- Keep tests focused, repeatable, and independent of undeclared local state.
- Test negative paths, timeouts, retries, permissions, malformed input, and
  resource limits where relevant.
- Do not weaken or delete a failing test merely to obtain a passing suite.

Automated testing is required where practical. If a test cannot be run, state
why and describe the strongest available alternative verification.

## 7. Git and Change Management

- Inspect `git status` and the relevant diff before making changes.
- Keep changes focused, reviewable, and logically grouped.
- Do not overwrite, reset, discard, or reformat unrelated user work.
- Do not rewrite history, force-push, push to a remote, create releases, or
  alter remote state unless explicitly requested.
- Review the final diff for accidental changes, secrets, generated files, and
  scope violations.
- Use clear commit messages when commits are requested; include intent and
  relevant verification information.

## 8. Dependency Management

- Inspect existing manifests, lockfiles, supported versions, and license policy
  before adding or upgrading dependencies.
- Prefer the smallest established dependency that solves the requirement.
- Do not add a package when the standard library or existing project dependency
  is sufficient.
- Pin or constrain versions according to project policy and update lockfiles
  consistently.
- Review transitive dependencies, maintenance status, security advisories,
  licensing, and compatibility before adoption.
- Test dependency upgrades and record behavioral or performance effects.
- Never install packages from untrusted sources or execute package code blindly.

## 9. Configuration and Environment Variables

- Keep code, non-secret defaults, environment-specific configuration, and
  secrets separate.
- Document required and optional variables, types, defaults, allowed values,
  and failure behavior.
- Validate configuration at startup and fail clearly for missing or invalid
  required settings.
- Never hard-code credentials, tokens, private keys, or passwords.
- Never expose secrets in source, logs, error messages, test output, commits,
  screenshots, or documentation.
- Use placeholders such as `<API_KEY>` in examples and redact sensitive output.
- Avoid logging complete environment dumps or request headers containing
  credentials.

## 10. Security

- Apply least privilege to files, services, credentials, tools, and API scopes.
- Treat all external input as untrusted and validate it before use.
- Protect against injection, path traversal, unsafe deserialization, SSRF,
  authentication bypass, authorization errors, and denial-of-service risks as
  applicable.
- Use secure defaults, encrypted transport, safe credential storage, and
  dependency/security scanning where available.
- Do not expose private data, authentication material, internal system details,
  or vulnerable proof-of-concept payloads unnecessarily.
- Obtain confirmation before security-sensitive or materially risky operations,
  including credential changes, production modifications, data deletion,
  irreversible migrations, or external messages.
- Report suspected security issues responsibly and avoid exploit actions outside
  the explicitly authorized scope.

## 11. Documentation

Document the audience, purpose, prerequisites, installation, supported versions,
configuration, environment variables, usage, examples, API contracts, failure
modes, security considerations, testing, deployment, rollback, limitations,
and troubleshooting.

Keep documentation synchronized with actual behavior. Mark examples as
illustrative when they have not been executed, and label generated or
unverified content.

## 12. Deployment and Operations

- Inspect the deployment target, runtime, secrets mechanism, networking,
  persistence, health checks, observability, rollback process, and approval
  requirements before changing deployment behavior.
- Build repeatable artifacts and record source revision, dependencies,
  configuration inputs, and build results.
- Use staging or an equivalent safe environment before production when
  practical.
- Define readiness, liveness, health, logging, metrics, tracing, alerts, and
  resource limits appropriate to the service.
- Use migrations that are reversible or have a documented recovery plan.
- Verify the deployed version, critical endpoints, logs, and health checks.
- Do not claim deployment success without observed evidence.
- Obtain explicit confirmation before production changes, irreversible
  operations, downtime, external notifications, or actions with meaningful cost.

## 13. Evidence, Uncertainty, and Honest Reporting

- Never fabricate code execution, tool access, test results, benchmarks,
  deployment status, logs, metrics, or verification.
- Report the exact command or method, environment, scope, and result when
  claiming a test or check was performed.
- Distinguish inspected, executed, tested, reproduced, verified, and
  independently confirmed states.
- If evidence is insufficient, say: “I don't have enough information to verify
  that.” Then identify the missing evidence and next check.
- Do not infer full-system correctness from a partial check.
- Report failures, skipped tests, flaky tests, unavailable tools, assumptions,
  limitations, and residual risks.

## 14. Standard Engineering Record Template

```text
# Engineering Record

Record ID:
Title:
Owner:
Created:
Last updated:
Status: Planned | In progress | Completed | Blocked

## Scope and acceptance criteria

Goal:
In scope:
Out of scope:
Inputs/outputs:
Acceptance criteria:
Assumptions:
Risks:

## Inspection

Files/components inspected:
Repository status/diff:
Runtime and environment:
Relevant dependencies/configuration:
Existing tests:

## Plan and implementation

Planned change:
Files changed:
Dependencies changed:
Configuration/environment changes:
Security considerations:
Rollback plan:

## Debugging, if applicable

Reproduction:
Isolation:
Root cause:
Fix:

## Testing and verification

Commands/methods:
Environment:
Tests executed:
Results:
Failures/skips:
Manual or deployment verification:
Remaining uncertainty:

## Documentation and handoff

Documentation updated:
Usage/deployment instructions:
Known limitations:
Follow-up actions:
Final report:
```
