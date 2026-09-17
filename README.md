# AI SNS MONEY FACTORY — PHASE 1 + PHASE 2

Scope: **SCOUT + AGENT ECONOMY RADAR** (PHASE 1) and **ANALYST + MONEY AGENT**
(PHASE 2), per spec v1.1. Not implemented yet (by design): CREATOR, PUBLISH,
GROWTH.

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
  analyst.py    ANALYST AGENT (§16): VIRAL DNA extraction -- validates the
                10 required angles (topic/hook/emotion/problem/desire/
                format/structure/comment trigger/shopping signal/
                replicability) and rejects a hook_principle that is a
                verbatim copy of a supplied source example ("복사 금지")
  money.py      MONEY AGENT (§12-15): checks a candidate against the fixed
                13-path revenue menu, requires a stated reason for every
                "viable" path, classifies MONETIZABLE only at >=3 viable
                paths (else TRAFFIC CONTENT), and maps viable candidates
                onto the 4-level PRODUCT OPPORTUNITY ladder (§15) -- the
                recommended next action always starts at LEVEL 1 (content),
                never jumps straight to a Micro SaaS
  pipeline.py   ingest_batch(): validate -> dedup -> score -> persist.
                analyze_batch(): attach ANALYST/MONEY output to candidates
                that already exist in the database (never creates new ones)
  report.py     Renders TOP 3 REPORT (§17), AGENT MONEY SIGNAL (§26), and
                -- once a candidate has been analyzed -- VIRAL DNA and
                MONEY AGENT REVENUE PATHS sections
  cli.py        `python3 -m scout.cli {ingest,analyze,report,list}`
tests/          40 unit tests covering scoring, dedup, validation, storage,
                ANALYST/MONEY validation, and report rendering
data/
  candidates.json         the persistent database (created on first ingest)
  research/YYYY-MM-DD.json  raw research batches (input to `ingest`)
  analysis/YYYY-MM-DD.json  raw VIRAL DNA + revenue-path batches (input to
                            `analyze`)
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

# 3. (optional, PHASE 2) Once you've reviewed the TOP candidates and want to
#    go deeper on one or two of them, run ANALYST + MONEY AGENT. This never
#    creates new candidates -- only deepens ones already in the database.
#    See data/analysis/2026-09-13.json for a real example (Mireye + the
#    Agent Skills money-gap candidate from the PHASE 1 research pass).
python3 -m scout.cli analyze data/analysis/2026-09-13.json --date 2026-09-13

# 4. Generate the daily report from everything seen on that date -- includes
#    VIRAL DNA / MONEY AGENT REVENUE PATHS sections for anything analyzed.
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
- `analyst.build_viral_dna` rejects a `hook_principle` that is byte-identical
  to a supplied `source_hook_example` — section 16's "복사 금지" isn't just
  a docstring, it's an enforced check.
- `money.build_money_analysis` rejects any revenue path marked `viable: true`
  that doesn't carry a non-empty `why` — MONEY AGENT can't call a path
  viable without a stated reason. A candidate with fewer than 3 such paths
  is classified `TRAFFIC CONTENT`, not padded with weak paths to look
  monetizable.

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
