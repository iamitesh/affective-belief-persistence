# Literature validation report

- Issue: [#4](https://github.com/iamitesh/affective-belief-persistence/issues/4)
- Validation date: 2026-08-15
- Result: **accepted for methodology handoff**
- Matrix: `data/research/literature-matrix.jsonl`
- Bibliography: `docs/research-citations.bib`

## Automated structural checks

The acceptance command parsed every nonblank JSONL row, enforced 25 required
fields, normalized uniqueness checks, validated canonical URL and identifier
formats, extracted BibTeX entry keys, checked key-set equality, and checked brace
balance.

```json
{
  "records": 34,
  "primary_technical": 22,
  "bib_entries": 34,
  "required_fields": 25,
  "errors": []
}
```

Results:

- required-field failures: 0;
- duplicate source IDs: 0;
- duplicate citation keys: 0;
- duplicate canonical URLs: 0;
- duplicate DOI/arXiv/OpenReview/ACL identifiers: 0;
- BibTeX-to-matrix key mismatches: 0;
- unbalanced BibTeX braces: 0;
- non-HTTPS canonical URLs: 0;
- unsupported identifier formats: 0.

## Identifier and link report

All 34 records have a canonical HTTPS URL and one stable DOI, arXiv,
OpenReview, or ACL Anthology identifier. Primary source pages were accessed
during the review. Some DOI publisher endpoints return bot challenges, 403s, or
robots denials to automated clients; these are reported as **crawler
unresolved**, not as broken identifiers.

| Status | Count | Meaning |
| --- | ---: | --- |
| Format valid | 34 | HTTPS URL plus supported stable identifier |
| Abstract/metadata spot-checked | 15 | Primary abstract or metadata inspected during this pass |
| Crawler unresolved in direct batch check | 8 | Publisher/OpenReview anti-bot response; previously discoverable through primary index/search |
| Confirmed broken | 0 | No malformed or dead canonical identifier found |

Before submission, rerun link resolution from a normal browser or DOI-aware
citation tool. Do not replace a DOI merely because the automated crawler is
blocked.

## Claim spot checks

At least ten central matrix claims were checked against primary-source abstracts
or metadata:

| Source | Checked claim | Outcome |
| --- | --- | --- |
| S01 Generative Agents | Memory, reflection, planning, and component ablations | Supported |
| S02 MemoryBank | Multi-session long-term companion memory and empathy-oriented response evaluation | Supported |
| S03 MemGPT | Hierarchical memory for multi-session chat | Supported |
| S04 SOTOPIA | Interactive social goals and difficult model performance | Supported |
| S05 AgentBench | Cross-environment action benchmark and model variation | Supported |
| S06 Reflexion | Episodic verbal feedback without weight updates | Supported |
| S08 LoCoMo | Up to 35 sessions and long-range memory gap | Supported |
| S09 LongMemEval | Extraction, temporal reasoning, update, and abstention abilities | Supported |
| S12 DisentQA | Parametric/contextual conflict and counterfactual disentangling | Supported |
| S15 Sycophancy | User-view agreement can displace truth | Supported |
| S21 Ross et al. | Judgments can persist after false feedback is discredited | Supported |
| S24 Arkes and Blumer | Prior investment affects continuation in reported tasks | Supported |
| S28 Nader et al. | Retrieval-dependent reconsolidation result in rat fear conditioning | Supported with species/task boundary |
| S31 Epley et al. | Anthropomorphism as a human inferential tendency | Supported |
| S33 Phang et al. | Mixed 28-day affective-use results and high-usage association | Supported |

No check supports human–LLM equivalence. Every human result is marked as
indirect conceptual evidence.

## Acceptance criteria

- [x] At least 30 relevant sources are evaluated (34).
- [x] At least 15 primary technical/scientific sources are included (34 primary
  or foundational; 22 technical).
- [x] Every source has a canonical link and stable identifier.
- [x] The closest prior work is explicitly compared.
- [x] The novelty statement describes a measurable combination and does not
  depend only on failed search.
- [x] Human psychological constructs are not transferred as equivalence claims.
- [x] Core design choices map to supporting or cautionary source IDs.
- [x] The final gap is non-anthropomorphic and measurable.
- [x] The bibliography key set parses with no duplicates or brace imbalance.
- [x] Positioning claims trace to matrix records.
- [x] Search queries, dates, and screened counts are recorded.
- [x] Contradictory, heterogeneous, and null-relevant findings are recorded.

## Acceptance decision

Issue #4 is accepted for internal workflow purposes. Issues #5 and #6 may start
using the following frozen handoff:

- recommended novelty claim: conservative statement in
  `docs/novelty-and-positioning.md`;
- terminology: `docs/terminology-map.md`;
- required controls: ten-item list in
  `docs/novelty-and-positioning.md`;
- source of truth: S01–S34 in the JSONL matrix;
- unresolved prior-art risks: the search-gap section in
  `docs/literature-matrix.md`.

Acceptance is not a publication claim. A refreshed search is still required
before paper submission.

