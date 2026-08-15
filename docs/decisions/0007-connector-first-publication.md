# ADR-0007: Connector-first GitHub publication while local Git is unsynchronized

- Status: Accepted
- Date: 2026-08-15
- Scope: Issue #2 delivery workflow

## Context

The active local workspace contains Issue #3 foundation files but is not a
trusted synchronized checkout of the remote repository. Treating local branch
metadata as authoritative could publish from the wrong base or imply a merge that
did not happen remotely.

## Decision

Use the connected GitHub publication workflow as the source of truth for remote
branch, pull-request, merge, and issue operations until local Git is explicitly
synchronized. Record remote commit identifiers and pull-request URLs in the task
journal. Local files remain the implementation workspace, not proof of remote
publication.

## Alternatives considered

- Force-push the local repository. This risks overwriting remote history.
- Assume local and remote branches match. Current evidence does not justify that
  assumption.
- Delay all work until a fresh clone is available. This would block useful local
  implementation and validation.

## Consequences

- Remote state is verified through GitHub before merge or publication claims.
- Publication may require content transfer rather than a normal local `git push`.
- Commit and PR evidence must be copied into the journal after each remote action.
- Once synchronization is established, a superseding ADR may restore the normal
  local branch, commit, push, and PR workflow.

## Verification

- [ ] The remote base SHA is checked before publishing Issue #2 changes.
- [ ] The journal records the created branch, commit SHA, PR, checks, and merge SHA.
- [ ] No remote merge is inferred solely from local Git status.

## References

- [Issue #2](https://github.com/iamitesh/affective-belief-persistence/issues/2)
- [Issue #3](https://github.com/iamitesh/affective-belief-persistence/issues/3)
- [Issue #2 task journal](../implementation/issue-2-task-journal.md)

