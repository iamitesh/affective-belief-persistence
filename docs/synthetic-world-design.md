# Synthetic world design

## Boundary

The world is a controlled measurement fixture, not a model of a real person.
Every identity, event, message, preference, and fact is synthetic. The contracts
contain no field for felt emotion, consciousness, attachment, grief, or a human
neural mechanism.

## Entities and invariants

| Entity | Purpose | Invariant |
| --- | --- | --- |
| Character | Stable synthetic participant | References only declared goals |
| Goal | Competing work, friendship, rest, learning, partner, or neutral objective | Priority lies in `[0,1]` |
| Resource budget | Conserved daily capacity | Ten non-carrying action points |
| Action option | Observable choice offered before language | Non-negative cost and deterministic consequence |
| Consequence | Reproducible resource and goal update | No stochastic or hidden update |
| Observable fact | Authoritative environment proposition | Stored separately from interpretations |
| Interpretation | Evidence-linked meaning | References facts in the same event |
| Memory candidate | Auditable external-memory input | References source facts and explicit eligibility |
| Condition variant | Only permitted treatment differences | Exact frozen mapping validated at runtime |
| Event | Day-level experimental input | Phase, matching group, provenance, menu, budget, and consequences required |
| Scenario | Versioned timeline and reference index | No dangling or duplicate IDs |

## Controlled world

Ari is the independently reset focal agent. Mira is scripted. Noah, Priya, and
the neutral ledger target provide competing friendship, work, and belief-control
contexts without another stochastic policy. Every day offers the same five
three-point actions under a ten-point budget. This preserves opportunity cost
without mechanically requiring a partner-directed choice.

The assigned formation treatment is represented only by
`ConditionVariant`: romantic instruction, autobiographical-memory eligibility,
and prior investment points. Baseline records keep every treatment inactive.
No event encodes the desired action or hypothesis direction.

## Fact and interpretation separation

An event fact such as “Mira and Ari completed a collaborative review” stays in
the immutable environment ledger. “The collaboration has romantic meaning” is
an interpretation with explicit fact references and `ledger_supported=false`.
Day 26 adds authoritative contradictory evidence; it does not rewrite earlier
facts. Reframing in later work may change an interpretation, never the ledger.

## Extension rules

New entities require a versioned runtime model, regenerated JSON Schema, valid
and invalid fixtures, cross-reference tests, and safety/provenance review. A new
treatment field requires a post-Gate-0 protocol version and deviation record.

Prohibited additions include real-person attributes, private histories,
unobserved emotion ground truth, desired post-shock answers in formation data,
free-form hidden state, nondeterministic consequences, and costs outside the
declared resource ledger.
