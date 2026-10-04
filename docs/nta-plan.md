# NTA addition: execution and acceptance plan

Authorized scope: add NTA public-transport schedules and realtime datasets using
the same research/implementation/review format as the original Person 2 pipeline.
This user request explicitly advances the NTA dataset work beyond the earlier
P0-first plan; it does not authorize claiming the transport router is built.

| Owner | Work |
| --- | --- |
| Source agent | Verify official URLs, licences, coverage, paired/all/Luas archive acquisition and provenance |
| Static GTFS agent | Stream tables to SQLite; preserve identity, calendars, timezone and overnight times; relational QA |
| Realtime agent | Verify API operations/authentication; bounded snapshots, normalization, freshness and protocol tests |
| Main agent | Explicit credential loading; manifest-to-database build, stop GeoJSON, static/realtime identifier audit; docs and integration checks |

Independent reviews rotate across ownership. Findings need a concrete code path
or reproducer, then a fix and a relevant regression check. The saved gstack
knowledge skill's evidence-led review and test-value guidance applies; no claim
of executing its uninstalled runtime is made.

## Gates

1. Primary-source verification: timetable versus live feed distinction, exact
   subscription header and client endpoints, licence/attribution, request limits.
2. Real archive fetch and validation: hashes, bounded streaming/expansion, safe ZIP
   members, no corrupted refresh replacing prior good data.
3. Actual feed import: service IDs/calendars, overnight times, stop hierarchy,
   unique identities, references and chronological sequences; memory-bounded
   SQLite import, atomic publication and source-change detection.
4. Realtime protocol checks: missing versus zero, stale/missing/future observations,
   cancellation/skip/no-data distinctions, safe auth errors and shared rate gate.
5. Integration: manifest verification, stop-point export, exact identifier audit
   and source fingerprints. Mismatches stay explicit.
6. Authenticated acceptance: own NTA key, successful supported endpoint responses,
   observed operator/entity coverage, actual static/realtime matching and age checks.
   This gate cannot be passed by synthetic fixtures or without credentials.

No account is created and no key is requested in chat. An optional credential-
availability question was sent; no key was present in the initial environment or
local `.env`. The user later supplied the key locally; both endpoints have now passed
authenticated fetches. Partial identifier conflicts remain documented. See [contract](transport-data-contract.md) and
[validation record](nta-validation.md) for final status.
