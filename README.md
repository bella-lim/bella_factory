# AI SNS MONEY FACTORY — PHASE 1

Scope: **SCOUT + AGENT ECONOMY RADAR** only, per spec v1.1 sections 33–36.
Not implemented yet (by design): ANALYST, MONEY AGENT, CREATOR, PUBLISH, GROWTH.

## Why this is split into two halves

Real trend discovery (searching GitHub/HN/Reddit/Naver, judging Korean Gap,
cross-verifying sources) is something only an agent with live web access can
do — it can't be hardcoded, and shouldn't be faked. So the system is split:

- **Research (non-deterministic, done by Hermes/Claude using WebSearch /
  WebFetch)**: find candidates, verify across >=2 independent sources where
  possible, check Korean-language coverage, judge Korean Gap / Money Gap,
  assign the rubric sub-scores from spec sections 10–11. Output: a raw
  candidate JSON file (see `data/research/2026-09-13.json` for a real,
  sourced example produced this way).
- **Pipeline (deterministic, this Python package)**: validate that raw JSON
  (real URLs required, no invented numbers, subscores in range), deduplicate
  against the persistent database, compute SCOUT SCORE / AGENT MONEY SCORE
  and tiers, flag PRODUCT OPPORTUNITY candidates, and render the daily
  report. This part never invents data — it only scores and stores what the
  research step already found.

## Layout

```
scout/
  models.py     Candidate schema + validation (rejects fabricated URLs,
                out-of-range scores, missing sources)
  scoring.py    SCOUT SCORE (§10) and AGENT MONEY SCORE (§11) + tiers
  dedup.py      Trend-cluster deduplication (same URL or fuzzy-matched name
                within the same track/category)
  storage.py    Persistent JSON database (data/candidates.json) — the
                long-term MONEY SIGNAL DATABASE asset from §27
  pipeline.py   ingest_batch(): validate -> dedup -> score -> persist
  report.py     Renders TOP 3 REPORT (§17) and AGENT MONEY SIGNAL (§26)
  cli.py        `python3 -m scout.cli {ingest,report,list}`
tests/          25 unit tests covering scoring, dedup, validation, storage,
                report rendering
data/
  candidates.json         the persistent database (created on first ingest)
  research/YYYY-MM-DD.json  raw research batches (input to `ingest`)
reports/
  YYYY-MM-DD.md   generated daily reports
```

## Running it

```bash
# 1. A research pass (done by Hermes with WebSearch/WebFetch) produces a raw
#    JSON batch matching the schema validated in scout/models.py. See
#    data/research/2026-09-13.json for a real example with sourced URLs.

# 2. Ingest it: validates, dedupes against history, scores, persists.
python3 -m scout.cli ingest data/research/2026-09-13.json --date 2026-09-13

# 3. Generate the daily report from everything seen on that date.
python3 -m scout.cli report --date 2026-09-13

# Inspect the whole database at any time:
python3 -m scout.cli list
python3 -m scout.cli list --track AGENT_ECONOMY

# Run the test suite:
python3 -m unittest discover -s tests
```

## What "never fabricate metrics" means here, concretely

- `models.validate_raw_candidate` rejects any candidate whose `url` isn't a
  real `http(s)://` link, or that has zero `sources`.
- `korean_gap` / `money_gap` are tri-state (`true` / `false` / `"UNKNOWN"`),
  never silently defaulted to a convenient value.
- Scores are the sum of explicit sub-scores (each capped at its spec
  weight) — there is no hidden multiplier or bonus.
- The report generator does **not** pad the TOP 3 or the AGENT MONEY SIGNAL
  section to hit a count. See `reports/2026-09-13.md`: it honestly reports
  "no candidate above ARCHIVE today" for the general trend track, because
  the one shopping candidate found (a foldable travel mouse trending
  abroad) turned out to already be distributed and reviewed in Korea
  (Gmarket/11st/Coupang/TechM) once checked — so it was scored down and
  archived instead of presented as an opportunity.

## Known limitations of this PHASE 1 pass

- Only 3 candidates were researched end-to-end (2 Agent Economy, 1 Shopping)
  as a demonstration of the full discover -> verify -> score -> store ->
  report pipeline; a production daily run would cover more of the AI /
  Shopping / Viral / Agent Economy tracks per §31 (생활불편 TOP 10 + Agent
  Economy TOP 5).
- Korean Gap / Money Gap checks used WebSearch, not the real Naver Search
  API (no credentials configured) — good enough to spot obvious cases
  (e.g. the mouse already sold on Korean marketplaces) but a production
  version should call the Naver API directly for precision.
- No Skill Safety Gate (§20) execution harness yet — flagged as `TEST`/`NO`
  hermes-compatibility rather than actually sandbox-testing anything,
  because PHASE 1 explicitly excludes installing or executing discovered
  skills.
