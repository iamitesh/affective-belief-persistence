# ADR-0009: Place the agent registry under `configs/agents/`

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2 configuration layout

## Context

Issue #2 names `configs/agents.yaml` as its expected registry artifact. Issue #3
already established `configs/agents/` as a directory for composable agent
configuration, so a file and directory cannot both occupy `configs/agents` on a
normal filesystem.

## Decision

Store the registry at `configs/agents/registry.yaml` and reference that exact path
from the workflow definition. Keep `configs/agents/foundation.yaml` intact for
the foundation experiment. The workflow loader validates that the registry stays
inside `configs/` and exists before scheduling begins.

## Alternatives considered

- Replace the Issue #3 directory with `configs/agents.yaml`. This would break the
  merged foundation configuration contract.
- Put the registry at an unrelated root name. That would avoid the collision but
  make the configuration hierarchy less predictable.

## Consequences

- The merged foundation remains backward compatible.
- Future registries or agent profiles can coexist in one directory.
- Documentation must call out the path deviation from Issue #2's singular-file
  example.

## Verification

- [ ] `load_agent_registry()` validates `configs/agents/registry.yaml`.
- [ ] The 48-hour workflow resolves the registry without path traversal.
- [ ] The foundation smoke configuration continues to resolve its agent file.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3](https://github.com/iamitesh/affective-belief-persistence/issues/3)
- [Issue #2 task journal](../implementation/issue-2-task-journal.md)
