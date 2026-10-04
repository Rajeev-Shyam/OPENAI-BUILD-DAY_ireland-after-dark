# Historical activity at a requested departure time

`data.pipeline.time_scores.load_time_scores(bundle_path, edges_path,
departure_time=aware_datetime)` validates the existing bundle and returns
`(rows_by_exact_string_edge_identity, time_slice)`. The routing adapter
`backend.routing.scores.load_edge_scores` accepts the same optional keyword and
returns the usual `ScoreBundle` with canonical integer OSM identities.

Omitting departure time preserves the bundle's original snapshot and supports
existing callers. A present bundle is always checked through the pipeline's
strict `load_scores` guard: exact graph fingerprint, complete unique edge IDs,
projected lengths, numeric ranges, coverage flags, observation coherence and
score formulas. Missing bundles preserve the existing unknown-data fallback;
corrupt present bundles fail rather than silently degrading to unknown.

An explicit departure must be a timezone-aware Python `datetime`. The instant
is converted to `Europe/Dublin` before selecting Monday=0 weekday and local
hour. The loader validates embedded counter profiles and their recorded source
hashes, then re-matches each edge against counters with observations for that
slot. It can choose a different counter when the original counter lacks data.
Missing bins produce null scores and false coverage flags, never fabricated
zero activity. Existing lighting values and the source file remain unchanged.
Input hashes are checked again before returning to reject concurrent replacement.

The retained publisher-timezone assumption is still unverified. Offset-aware
inputs resolve request-time ambiguity, not ambiguity in the historical source.
Both repeated autumn hours select the same historical weekday/hour bin; the
pipeline excluded ambiguous source observations. Scores describe historical
activity, not live counts or personal safety.

## Integration boundary and cost

This operation projects the full exported graph to verify lengths and, for a
new slot, repeats geometry matching. It is intended for batch preparation or
cache loading, not to be called for every journey request. Cache by bundle hash,
edge-export hash and local weekday/hour, invalidate on either input change,
and bound cache size. Precomputed slices or a persisted spatial association
index can replace the expensive step after profiling.

`GraphStore` and the HTTP API do not yet select departure-time slices. This
module makes the data-side capability available; it does not claim that the
frontend time picker currently changes route activity scores.

Run the contract tests in the shared Python 3.12 environment:

```sh
python -m pytest tests/test_time_scores.py tests/test_build.py tests/test_routing.py
```
