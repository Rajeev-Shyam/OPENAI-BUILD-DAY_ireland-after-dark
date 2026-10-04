# Person 2: execution and acceptance plan

Scope updated by the user's task split: the routing team supports Ireland; this
pipeline supplies verified local observations without extrapolating Dublin data
nationally. Existing starter brief describes an earlier, narrower proposal.

## Ownership

| Workstream | Owner | Deliverables |
| --- | --- | --- |
| Source acquisition and evidence | Sources agent | Download CLI, source registry, hashes, licences, access/quality notes |
| Lighting | Lighting agent | Clean assets, projected edge matching, density/proximity measures, coverage semantics, tests |
| Historical pedestrian activity | Footfall agent | Valid pedestrian series, coordinate mapping, weekday/hour profiles, spatial support, tests |
| Integration and review | Main agent | Graph-edge contract, pipeline CLI, reproducible handoff, end-to-end checks, unresolved issues |

All contributors use the local gstack knowledge library's engineering-review,
source-grounding, failure-inventory and test-value principles. The gstack runtime
is not installed; this is not a claim that its automated commands have run.

## Decisions before implementation

- Person 1 owns the walking graph. We accept their WGS84 edge GeoJSON with stable
  `(u, v, key)` identifiers, rather than download a different graph whose edge IDs
  would not join. A graph fingerprint accompanies every export.
- Use EPSG:2157 for metre-based geometric operations, with explicit longitude,
  latitude axis ordering. Degree distances are never treated as metres.
- Observation proximity, source applicability, inventory completeness and freshness
  are different facts. A nearby lamp is positive evidence; absent lamps do not
  prove a surveyed street has none. Footfall has local spatial and temporal support.
- Unknown scores are null. Recorded zero readings remain zero. No synthetic
  observation is mixed into real-data output.
- Export weekday/hour profiles as well as a selected time's edge scores. A static
  edge file is valid only for its declared weekday/hour; callers must not reuse it
  for arbitrary journey times.
- Scores are documented prototype transformations, not validated measures of
  personal security. Confidence aggregation belongs to Person 4.

## Acceptance gates

1. **Acquisition:** real source downloaded by command; content/schema checked;
   URL, retrieval time, hash and source metadata recorded; invalid fetch cannot
   silently become a valid cached dataset.
2. **Cleaning:** coordinate bounds, schema, duplicate IDs, missing values, misleading
   labels, overlapping counter totals and timezone assumptions are handled explicitly.
3. **Spatial/temporal matching:** tests cover metre distances, partial edge support,
   no support outside source coverage, missing hour bins, reverse/parallel edge IDs.
4. **Handoff:** deterministic output shape, no NaN/Infinity, preserved identities,
   input fingerprints, inspectable quality report and reproducible command.
5. **Review:** separate review of calculations and CLI behaviour, real-source run,
   regression tests for discovered defects, and clear distinction between a tested
   pipeline and untested integration with the routing team's eventual graph.

P1 enrichment follows a working P0 handoff. P1/P2 source research can happen now;
unavailable official downloads are recorded as blocked, never replaced with
fabricated data. No route API, frontend, transport engine or crime scoring is
implemented as part of Person 2's work.

## Current result

The user subsequently authorized the NTA schedule/realtime dataset addition.
Its separate [execution plan](nta-plan.md) and [handoff contract](transport-data-contract.md)
extend the data scope while keeping transport routing outside this implementation.

The three specialist workstreams and integration implementation have landed in
the local working tree. Core downloads and processing are exercised against real
source bytes, with synthetic geometry for isolated end-to-end validation. An
independent review found defects that were reproduced and fixed. See
[the validation record](data-validation.md) for executed evidence, unresolved
acceptance gates and the exact boundary of completion; see
[the handoff contract](edge-data-contract.md) for commands and field semantics.
