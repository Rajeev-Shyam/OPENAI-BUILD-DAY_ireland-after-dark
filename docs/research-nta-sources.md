# NTA transport source audit

Verified 4 October 2026. This audit applies the saved gstack validation method: use primary evidence, inspect real inputs, test failure paths, and distinguish implemented behaviour from live-service acceptance.

## Static acquisition

The [NTA catalogue](https://data.gov.ie/dataset/nta-gtfs) and its [machine-readable metadata](https://data.gov.ie/api/3/action/package_show?id=nta-gtfs) identify the publisher and CC BY 4.0 licence. The [official TFI public transport index](https://www.transportforireland.ie/transitData/PT_Data.html) provides these directly linked archives, with attribution to National Transport Authority:

| Registry source | Official download | Scope |
| --- | --- | --- |
| `nta_gtfs_realtime` | [GTFS_Realtime.zip](https://www.transportforireland.ie/transitData/Data/GTFS_Realtime.zip) | **Static** schedules for realtime operators; default for integration |
| `nta_gtfs_all` | [GTFS_All.zip](https://www.transportforireland.ie/transitData/Data/GTFS_All.zip) | Published all-operator static feed |
| `nta_gtfs_luas` | [GTFS_LUAS.zip](https://www.transportforireland.ie/transitData/Data/GTFS_LUAS.zip) | Luas-only static feed for small real-data validation |

Download without credentials:

```sh
.venv/bin/python -m data.pipeline.nta_download --source nta_gtfs_realtime
.venv/bin/python -m data.pipeline.nta_download --source nta_gtfs_all
.venv/bin/python -m data.pipeline.nta_download --source nta_gtfs_luas
```

`--refresh` explicitly fetches a new generation; otherwise a valid local snapshot is reused offline. Default directory: `data/raw/nta/`. Each source has an immutable `snapshots/<source>-<sha256>.zip`, atomic `<source>.manifest.json`, and repairable `<source>.zip` convenience alias. The manifest records source/resolved URL, publisher/licence, hash, byte counts, retrieval timestamp, ETag, Last-Modified and ZIP inventory. Cache validation repeats hash and archive checks. Refresh failure preserves the previous manifest.

Acquisition uses bounded streaming, never extracts paths, validates all member CRCs, rejects duplicate/nested/unsafe members, and requires core tables plus a calendar table. Limits are 512 MiB compressed, 4 GiB expanded and 100 members. Bounds are implementation limits, not claims about publisher size. GTFS table semantics, references and service calendars require the separate static processor before downstream use.

## Observed snapshots (direct inspection, not catalogue estimates)

| Observation | Luas | Realtime-compatible static |
| --- | --- | --- |
| Compressed bytes | 1,010,252 | 144,073,521 |
| Expanded bytes | 5,025,058 | 756,618,259 |
| SHA-256 | `5712cc24bf43958a0b08a1b055fb07dea9484b9bca021d14f59f2f41fad26761` | `3d103bfb5e2477691ddbb1eff7d03d4296598e58540c67f56eeb6d66e0c99a78` |
| `feed_start_date` / `feed_end_date` | 20261003 / 20271003 | 20261003 / 20271003 |
| `feed_version` | `892A3408-F422-4978-8896-7420CF625122` | `892A3408-F422-4978-8896-7420CF625122` |

Both contain ten root-level text tables, including `shapes.txt` and `translations.txt`. Full CRC validation passed for both. The Luas archive additionally passed a real downloader invocation and a cached invocation. The paired archive also passed the production streaming downloader, with canonical archive and manifest under `data/raw/nta/`; its hash matched the independently downloaded copy. The static processor's semantic acceptance is recorded separately in integration evidence. `GTFS_All.zip` also passed the production downloader and full CRC validation: 179,594,769 compressed bytes, 871,521,603 expanded bytes, SHA-256 `e3915c7dd1ecce224a6cc177e7005698aa51785c358e5aa50249eb5446fe1430`. Its ten members use the same feed version and dates shown above. The canonical archive and manifest are under `data/raw/nta/`. Its agency table contains 104 rows, including TFI Local Link and private operators beyond the realtime subset; all use `Europe/London`. These are agency rows, not a count of unique companies. Semantic import results are documented separately.

The paired archive lists seven agency rows: Dublin Bus, Luas, Bus Éireann, Bus Éireann Waterford, Irish Rail, and two Go-Ahead rows. These are feed observations, not a promise every service or vehicle is represented live. All observed agency timezones are `Europe/London`; preserve source timezone semantics rather than overwriting them. Feed date bounds do not mean every trip operates every day: calendars and exceptions determine actual service.

## Freshness, realtime pairing and coverage

[NTA's migration notice](https://www.nationaltransport.ie/news/attention-developers-upgrade-to-gtfs-realtime-api/) explains that internally generated IDs can change between static generations. Match realtime against the corresponding schedule period/version; updates may occur daily and the frequency is not guaranteed. Refresh static data and measure joins; successful transport HTTP responses alone do not prove identifier compatibility. Last-Modified dates describe an HTTP object, not current service validity.

The [production developer portal](https://developer.nationaltransport.ie/) requires registration and subscription keys for realtime APIs. Static files are publicly downloadable; this does not remove realtime authentication or quota requirements. The portal's home-page fair-use link points to an explicitly `usagepolicy-old` page, so do not treat its old quota as an independently verified current subscription limit. Realtime client research and authenticated acceptance must establish current endpoints, payloads and limits separately.

No island-wide completeness claim is supported by these observations. The all-operator label describes NTA's published selection, and the smaller realtime-compatible file is a subset. In particular, neither inspected paired nor all-operator archive contains a Translink agency row. This does not establish that no cross-border stops exist, nor does it establish Northern Ireland coverage. Use observed stops, operating service dates and measured realtime joins to describe availability at a journey's time and location. Transport coverage is separate from Dublin lighting/footfall coverage and cannot fill those missing sources.
