# AI SNS MONEY FACTORY — PHASE 1 + PHASE 2 + PHASE 3

Scope: **SCOUT + AGENT ECONOMY RADAR** (PHASE 1), **ANALYST + MONEY AGENT**
(PHASE 2), and **CREATOR + FINAL EDITOR** (PHASE 3), per spec v1.1. Not
implemented yet (by design): Telegram Approval, PUBLISH, GROWTH. Nothing in
this repo can publish content anywhere — the furthest any candidate gets is
`PREVIEW_READY`, which is a precondition for a human to look at it, never
an approval (spec section 21 requires an explicit, separate publish
approval that this pipeline does not perform).

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
  creator.py    CREATOR AGENT (§18): validates Threads drafts (exactly the
                3 required versions -- info/experience/shopping -- each
                <=500 chars), Naver Blog drafts (3 SEO titles, keywords,
                hook/problem/situation/cause/solution/selection
                criteria/FAQ/closing), and YouTube Shorts drafts (5 titles,
                3 thumbnail texts, the 0-3/3-15/15-40/40-52/52-60s
                structure, B-roll/subtitles/video prompt/description/tags).
                Any subset of the 3 platforms may be supplied.
  editor.py     FINAL EDITOR (§19): scans drafted content for banned
                exaggeration phrases (무조건/100%/보장합니다...) and AI-style
                tells (안녕하세요, 오늘은.../결론적으로...), flags near-duplicate
                Threads versions, requires an ad-disclosure marker when
                MONEY AGENT marked an affiliate path viable, and -- for
                AGENT_ECONOMY candidates -- requires license and
                security_notes to be recorded. Never sets an "approved"
                flag; status tops out at PREVIEW_READY, which is a
                precondition for human preview, not a publish approval
  pipeline.py   ingest_batch(): validate -> dedup -> score -> persist.
                analyze_batch(): attach ANALYST/MONEY output to candidates
                that already exist in the database (never creates new
                ones). create_batch(): attach CREATOR drafts to existing
                candidates and immediately run FINAL EDITOR against them
  report.py     Renders TOP 3 REPORT (§17), AGENT MONEY SIGNAL (§26), and
                -- once run -- VIRAL DNA, MONEY AGENT REVENUE PATHS,
                CREATOR OUTPUT, and FINAL EDITOR CHECK sections
  cli.py        `python3 -m scout.cli {ingest,analyze,create,report,list}`
tests/          64 unit tests covering scoring, dedup, validation, storage,
                ANALYST/MONEY/CREATOR/EDITOR validation, and report
                rendering
data/
  candidates.json         the persistent database (created on first ingest)
  research/YYYY-MM-DD.json  raw research batches (input to `ingest`)
  analysis/YYYY-MM-DD.json  raw VIRAL DNA + revenue-path batches (input to
                            `analyze`)
  content/YYYY-MM-DD.json   raw Threads/Naver/Shorts draft batches (input
                            to `create`)
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

# 4. (optional, PHASE 3) Once MONEY AGENT has classified something
#    MONETIZABLE, draft the actual platform content and run it through
#    FINAL EDITOR. See data/content/2026-09-13.json for a real example
#    (3 Threads versions, a Naver Blog draft, a YouTube Shorts script --
#    all for the Agent Skills money-gap candidate). This never publishes
#    anything; the furthest a candidate gets is PREVIEW_READY.
python3 -m scout.cli create data/content/2026-09-13.json --date 2026-09-13

# 5. Generate the daily report from everything seen on that date -- includes
#    VIRAL DNA / MONEY AGENT REVENUE PATHS / CREATOR OUTPUT / FINAL EDITOR
#    CHECK sections for anything analyzed / drafted.
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
- `creator.build_content` refuses a Threads draft missing any of the 3
  required versions (info/experience/shopping), and `editor.py` flags two
  versions that are near-duplicates of each other — CREATOR can't satisfy
  "3 versions" by copy-pasting one angle three times.
- The "경험/공감형" (experience) Threads draft for the Agent Skills
  candidate deliberately avoids a fabricated first-person success story —
  it's written in second person, addressed to the reader's likely search
  frustration, because nobody involved has actually sold a Skill yet. A
  real first-person account should replace it once one exists.
- FINAL EDITOR never sets an `approved` field. `content_status` stops at
  `PREVIEW_READY` / `NEEDS_REVISION` — section 21's explicit human publish
  approval is a separate step this repo doesn't implement.

## Known limitations of PHASE 1-3 so far

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
- CREATOR drafts were produced for only 1 of the 2 MONETIZABLE candidates
  (Agent Skills) as a demonstration; Mireye's drafts are left for a future
  run.
- FINAL EDITOR's checks are all pattern/structure-based (banned phrases,
  similarity ratios, required fields). It cannot verify factual accuracy,
  judge whether a claim is actually exaggerated in context, or catch AI
  style beyond the fixed phrase list — those still need a human pass
  before section 21's publish approval.
