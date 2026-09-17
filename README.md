# AI SNS MONEY FACTORY — PHASE 1 through PHASE 5 (full loop)

Scope: **SCOUT + AGENT ECONOMY RADAR** (PHASE 1), **ANALYST + MONEY AGENT**
(PHASE 2), **CREATOR + FINAL EDITOR** (PHASE 3), **Telegram Approval**
(PHASE 4), and **PUBLISH + GROWTH + FEEDBACK** (PHASE 5), per spec v1.1.
Every phase in the spec now has code. `scout.cli publish` is the only
thing in this repo that can post something externally, and it refuses to
run for any candidate whose `approval.status != "APPROVED"` — a real human
decision recorded in PHASE 4, never something this pipeline decides for
itself. `scout.cli record-metrics` (GROWTH) refuses to run for any
candidate that was never actually `PUBLISHED`.

## PUBLISH platform capability is honest, not assumed

- **Threads**: real (Meta's Graph API, `graph.threads.net`, documented
  2-step container→publish flow). Needs Tech Provider Verification and a
  `threads_content_publish`-scoped token from Meta.
- **YouTube Shorts**: real (YouTube Data API v3, resumable upload). But
  CREATOR (§18) only ever produces a `video_prompt` / script for Shorts,
  never a rendered video file — this pipeline has no video-generation
  step. `publish --platform youtube_shorts` requires `--video-file` to
  already exist; if you haven't rendered one, it fails immediately with
  that reason rather than doing anything.
- **Naver Blog**: **not supported**, always. There is no current,
  reliably-documented public API for a third party to create a post on an
  arbitrary personal Naver Blog — the only mechanism found in research was
  a MetaWeblog/XML-RPC integration from a 2010 blog post, with no
  confirmed 2026 support. `publish --platform naver_blog` always returns
  `NOT_SUPPORTED` with that explanation rather than pretending to work.
  Publish the `naver_blog` draft in `data/content/*.json` manually through
  Naver's own blog editor.

## PHASE 4 needs real Telegram credentials, and this sandbox can't use them

`scout/telegram_bot.py` and `scout/webhook_server.py` talk to
`api.telegram.org`. This development sandbox's egress policy blocks that
host outright (`curl https://api.telegram.org` → 403 from the proxy, not a
code bug) — so **no live send or webhook was tested from here**. Everything
network-touching is split out from the pure logic so the pure parts (message
formatting, keyboard building, callback parsing, decision application) are
fully unit-tested without needing network at all; only the thin
`call_telegram_api` wrapper and the two functions built on it
(`send_approval_request`, `answer_callback_query` /
`edit_message_after_decision`) are unverified beyond code review. Run those
from an environment that can actually reach Telegram (your own machine, a
server, GitHub Actions) with `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` /
`TELEGRAM_WEBHOOK_SECRET` set (copy `.env.example` to `.env`, fill in real
values, never commit `.env`).

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
  telegram_bot.py   Telegram Approval (§21). Pure, network-free functions:
                format_approval_message / build_inline_keyboard /
                build_send_payload (the 👀 미리보기 / ✏️ 수정 / ✅ 게시 승인 /
                🗑️ 폐기 buttons), parse_callback_data, record_approval_
                requested (refuses unless content_status is PREVIEW_READY),
                and apply_decision -- the only function that can ever set
                approval.status to APPROVED, and only for a real decision
                string, never invented. The network-touching functions
                (call_telegram_api, send_approval_request, answer_
                callback_query, edit_message_after_decision) are thin
                wrappers around those pure functions.
  webhook_server.py A long-running stdlib http.server process (unlike the
                rest of this CLI) that receives Telegram's callback_query
                updates, rejects any request without a matching
                X-Telegram-Bot-Api-Secret-Token header, and otherwise just
                calls apply_decision() + acks back to Telegram.
  publish.py    PUBLISH (§22+). guard_approved() is the single gate every
                publisher goes through first -- refuses unless
                approval.status == "APPROVED". publish_threads (real
                Graph API), publish_youtube_shorts (real Data API v3,
                needs a video file this pipeline never renders),
                publish_naver_blog (always NOT_SUPPORTED, see above, with
                the reason recorded rather than a fake success)
  growth.py     GROWTH + FEEDBACK (§22-25). guard_published() refuses
                anything never actually PUBLISHED. compute_baseline()
                takes the median of the account's own comparable posts
                (same platform + window) and refuses to guess a baseline
                below MIN_BASELINE_SAMPLE_SIZE=3 data points -- returns
                ratio=None/band="UNKNOWN" rather than fabricating one from
                too little history. band_for_ratio() applies the §23
                thresholds (<0.7 UNDERPERFORM, 0.7-1.5 NORMAL, 1.5-3
                WINNER, 3-5 HOT, 5+ BREAKOUT). compute_money_performance()
                keeps content and money verdicts on separate axes (§24) --
                judged purely on conversions, never blended with views.
                generate_feedback() is a fixed lookup table over
                (content tier, money verdict) -> rule-based notes for
                SCOUT/MONEY/CREATOR, not generated text.
  report.py     Renders TOP 3 REPORT (§17), AGENT MONEY SIGNAL (§26), and
                -- once run -- VIRAL DNA, MONEY AGENT REVENUE PATHS,
                CREATOR OUTPUT, FINAL EDITOR CHECK, TELEGRAM APPROVAL,
                PUBLISH STATUS, GROWTH, and FEEDBACK LOOP sections
  cli.py        `python3 -m scout.cli {ingest,analyze,create,
                request-approval,record-decision,set-webhook,
                serve-webhook,publish,record-metrics,report,list}`
tests/          117 unit tests covering scoring, dedup, validation,
                storage, ANALYST/MONEY/CREATOR/EDITOR/Telegram-approval/
                publish/growth validation, and report rendering -- all
                network-free
data/
  candidates.json         the persistent database (created on first ingest)
  research/YYYY-MM-DD.json  raw research batches (input to `ingest`)
  analysis/YYYY-MM-DD.json  raw VIRAL DNA + revenue-path batches (input to
                            `analyze`)
  content/YYYY-MM-DD.json   raw Threads/Naver/Shorts draft batches (input
                            to `create`)
reports/
  YYYY-MM-DD.md   generated daily reports
.env.example      required Telegram + publish-platform env var names (no
                  real values)
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

# 5. (optional, PHASE 4) Once content is PREVIEW_READY, send it to a human
#    for Telegram Approval. Needs real credentials -- see .env.example --
#    and network access to api.telegram.org, which this sandbox lacks.
set -a; source .env; set +a   # TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
python3 -m scout.cli request-approval agent-economy-agent-skills

#    Run a webhook server somewhere reachable by Telegram (needs a public
#    HTTPS endpoint in front of it -- this process itself speaks plain
#    HTTP) to apply button-press decisions automatically:
python3 -m scout.cli set-webhook https://your-public-host.example.com
python3 -m scout.cli serve-webhook --port 8443

#    Or, without a live server, record a decision manually once you know it
#    (e.g. the human told you what they tapped): still requires a prior
#    request-approval call -- you can't approve something never actually
#    sent for review.
python3 -m scout.cli record-decision agent-economy-agent-skills approve --by bella

# 6. (optional, PHASE 5 PUBLISH) Once approval.status is APPROVED, publish.
#    Needs real per-platform credentials -- see .env.example -- and network
#    access this sandbox lacks. Refuses to run at all if not APPROVED.
python3 -m scout.cli publish agent-economy-agent-skills --platform threads --version info
python3 -m scout.cli publish agent-economy-agent-skills --platform naver_blog        # always NOT_SUPPORTED
python3 -m scout.cli publish agent-economy-agent-skills --platform youtube_shorts --video-file ./short.mp4

# 7. (optional, PHASE 5 GROWTH) Once a platform actually shows PUBLISHED,
#    record measurements at fixed windows (1H/6H/24H/72H/7D) and this
#    immediately computes the performance ratio against the account's own
#    history, a separate content/money verdict, and rule-based feedback.
#    Refuses to run for anything never actually PUBLISHED. A batch JSON
#    file, same shape as ingest/analyze/create:
#    [{"candidate_id": "...", "window": "24H",
#      "metrics": {"platform": "threads", "views": 500, "likes": 10, ...
#                  "conversions": 0}}]
python3 -m scout.cli record-metrics data/growth/2026-09-13.json

# 8. Generate the daily report from everything seen on that date -- includes
#    VIRAL DNA / MONEY AGENT REVENUE PATHS / CREATOR OUTPUT / FINAL EDITOR
#    CHECK / TELEGRAM APPROVAL / PUBLISH STATUS / GROWTH / FEEDBACK LOOP
#    sections for anything analyzed / drafted / requested / published /
#    measured.
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
  approval is a separate step, implemented in PHASE 4 as a real Telegram
  button press, not this pipeline deciding on its own.
- `telegram_bot.apply_decision` is the **only** function anywhere in this
  codebase that can set `approval.status = "APPROVED"`, and it only runs in
  response to an `action` string that came from an actual Telegram
  `callback_query` (via the webhook) or a human explicitly telling the
  operator what they tapped (via `record-decision`). `record_approval_
  requested` refuses to even start the flow unless `content_status ==
  "PREVIEW_READY"` — you can't request approval on content FINAL EDITOR
  hasn't passed.
- `publish.guard_approved` is called first by every publisher, before any
  network code runs — `python3 -m scout.cli publish agent-economy-agent-
  skills --platform naver_blog` on an unapproved candidate fails
  immediately with "not APPROVED", verified by actually running it (see
  "Known limitations" below).
- `publish_naver_blog` never returns `PUBLISHED` — there is no code path
  that fakes a post id or URL for a platform with no real write API.
- `growth.guard_published` refuses to run for any candidate with no
  `PUBLISHED` entry in `publish_status` — verified live (`scout.cli
  record-metrics` against the unpublished Agent Skills candidate fails
  immediately with "no PUBLISHED platform").
- `growth.compute_baseline` returns `baseline=None` (and the report prints
  "baseline needs N of at least 3 comparable posts... not fabricated")
  below `MIN_BASELINE_SAMPLE_SIZE = 3` — there is no fallback that invents
  a baseline from 1 or 2 data points, or from a different platform/window.
- `growth.compute_money_performance` never looks at `views`/`likes` to
  decide the money verdict, only `conversions` — section 24's whole point
  (a viral winner can be a money failure) would break if the two were
  blended.
- `growth.generate_feedback` is a fixed dict lookup over all 9 (content
  tier × money verdict) combinations, not generated prose — every
  combination is covered (tested), so it can't silently fall through with
  no advice.

## Known limitations of PHASE 1-5 so far

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
- No PHASE 4 Telegram send or webhook call has actually been exercised
  end-to-end — this sandbox cannot reach `api.telegram.org` (see the
  section above). The pure logic (message/keyboard building, callback
  parsing, decision state machine) has 79 passing unit tests; the network
  glue around it (`call_telegram_api` and everything built on it) has not
  been run against the real API and should be smoke-tested first in an
  environment with network access, before relying on it.
- `webhook_server.py` has no automated tests of its own (it's a thin
  `BaseHTTPRequestHandler` wrapper around already-tested pure functions,
  and isn't practical to unit-test without a real socket) — verify it
  manually (e.g. `curl` a fake Telegram update at it locally) before
  pointing a real bot's webhook at it.
- PHASE 4 stops at recording a decision; PHASE 5 (PUBLISH) is what
  actually posts, described above.
- Same network constraint as PHASE 4: `publish_threads` and
  `publish_youtube_shorts` reach external hosts this sandbox's egress
  policy blocks, so neither has been exercised end-to-end against the
  real APIs. Only the approval gate, payload/metadata builders, and the
  `naver_blog` NOT_SUPPORTED path were actually run (91 passing unit
  tests, all network-free) — smoke-test the two real integrations from an
  environment with network access and real credentials before relying on
  them.
- No candidate has actually been through the full loop (approve → publish
  → measure) in this session: Mireye and the Agent Skills candidate are
  `PREVIEW_READY`/analyzed but neither has been approved, published, or
  measured. GROWTH was deliberately **not** demonstrated with fake numbers
  for them — that would mean literally fabricating view/click/conversion
  counts for posts that don't exist, which is exactly what this whole
  project has avoided at every phase. `tests/test_growth.py` demonstrates
  the logic with clearly-synthetic test fixtures instead (the normal,
  correct place for made-up numbers).
- `growth.compute_money_performance`'s money verdict is intentionally
  simple (conversions > 0 → WINNER, conversions == 0 → FAILURE,
  conversions untracked → UNKNOWN) to match the spec's own examples
  exactly (§24). It doesn't yet weigh revenue amount, click-through rate,
  or platform-specific nuance — a production version might want a richer
  rule once real conversion data exists to calibrate against.
- `growth.generate_feedback`'s notes are fixed Korean strings per
  (tier, verdict) combination, not tailored to the specific candidate or
  content (e.g. it won't reference the actual CTA text that underperformed)
  — CREATOR would need real drafts alongside the feedback to act on it,
  the same way a human editor would re-open `data/content/*.json`.
