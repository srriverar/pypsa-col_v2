# Pinned source dependency

`colombiacongestionV2/` is the user-requested source clone, locked to
`a6fcf7622249f555d81e293a11f05b8a6aee7c39`. It is bundled in the delivery ZIP
without Git internals and fetched by `scripts/bootstrap_sources.py` in a new
checkout. It is not vendored into the new Git history or silently relicensed.
See `config/sources.lock.json` and `THIRD_PARTY_NOTICES.md`.

The official API_XM and original Grid2Poster repositories were also cloned and
inspected during development; their commit IDs are recorded in the source lock.
Only necessary metadata/notices are retained. Runtime rendering uses the pinned
Colombian adaptation, not the full upstream poster gallery.
