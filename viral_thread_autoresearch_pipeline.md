# Directive: Viral Thread Autoresearch Pipeline

Autonomous daily loop that transforms Obsidian research dossiers into viral Threads posts.
Optimizes for **virality** by mutating writing style (the challenger) across iterations and scoring against a composite metric.

## Architecture

```
Layer 1 (Directive):  This file + directives/thread_pipeline.md
Layer 2 (Orchestration): LLM agent reads this, calls scripts in order
Layer 3 (Execution):  Python scripts in execution/
```

## Constraints

| Parameter | Value | Rationale |
|:---|:---|:---|
| Max variants/day | 10 | Groq free-tier budget |
| LLM calls/day | 10 | 1 call = 1 variant (mutate + redraft combined) |
| Posts per thread | ≤500 chars each | Threads platform limit |
| Publishing cadence | 1 thread/day | Anti-bot + Buffer free tier (10 queued/channel) |
| Posting time | 09:00 WIB | `POSTING_TIME` in `.env` |
| Voice | gue/lo, "The Relatable Intellectual" | From `voice_profile.json` |
| Forbidden | AI-isms, saya/Anda, generic openers | Enforced by `editorial_checker.py` |

## Inputs

| Input | Source | Purpose |
|:---|:---|:---|
| Research dossier | `D:\Pribadi\Obsidian\Writing\Research\<topic>\Source_of_Truth.md` | Factual backbone |
| Essay draft | `Research\<topic>\Essay_*_Threads.md` | Raw long-form to split into thread |
| Voice profile | `execution/voice_profile.json` (generated from @xpajonx + essays) | Style constraints |
| Shadow analytics | `execution/shadow_analytics.py` output (@m.fauzan.aziz) | Historical engagement calibration |
| Trend signals | `threads_tracker_id.py` output | Cultural moment awareness |

## The Autoresearch Loop

```
INGEST  → Read Source_of_Truth + essay + voice + analytics
DRAFT   → thread_formatter.py: essay → thread_draft.json (baseline)
SCORE   → virality_scorer.py: compute virality_score (deterministic, no LLM)
MUTATE  → style_mutator.py: 1 Groq call, change CRIBS params, respect voice
DECIDE  → score > best? keep : discard
LOG     → results.tsv (variant, score, mutation, status)
REPEAT  → Up to 10x/day
PUBLISH → buffer_publisher.py: best variant → Buffer queue (1/day, 09:00 WIB)
```

## CRIBS Challenger Parameters (Mutation Space)

| Parameter | Options | What It Changes |
|:---|:---|:---|
| `hook_type` | `curiosity_gap`, `pattern_interrupt`, `contrarian`, `statistic_bomb`, `personal_anecdote` | Opening post strategy |
| `vocab_register` | `street` (gue/lo heavy), `balanced`, `formal` | Indonesian register dial |
| `rhythm` | `staccato` (short punchy), `flowing` (narrative), `mixed` | Sentence cadence |
| `data_density` | `low` (1 stat/3 posts), `medium`, `high` (1 stat/post) | Research integration |
| `emotional_arc` | `tension_release`, `escalating`, `bookend` | Thread-level pacing |

## Virality Score (Metric: higher = better)

Composite 0.0–1.0. All sub-scorers are **deterministic** (no LLM call):

```
virality_score = (
    0.25 * hook_score        # First post: question/stat/pattern-interrupt present?
  + 0.20 * readability_score # Sentence length variance, no text walls
  + 0.15 * data_density      # Specific numbers/stats/citations count
  + 0.15 * emotional_arc     # Sentiment variance across posts (lexicon-based)
  + 0.15 * shareability      # ≥2 posts work as standalone quotes?
  + 0.10 * platform_fit      # All posts ≤500 chars, CTA present, no orphans
)
```

## Execution Scripts

| Script | Status | Purpose |
|:---|:---|:---|
| `execution/config.py` | **NEW** | Loads `.env`, paths, retry logic |
| `execution/voice_extractor.py` | **NEW** | One-time: @xpajonx + essays → `voice_profile.json` |
| `execution/thread_formatter.py` | **NEW** | Essay → thread posts (≤500 chars) |
| `execution/virality_scorer.py` | **NEW** | Deterministic composite scorer |
| `execution/style_mutator.py` | **NEW** | CRIBS challenger (1 Groq call/variant) |
| `execution/shadow_analytics.py` | **NEW** | @m.fauzan.aziz Tavily engagement scrape |
| `execution/buffer_publisher.py` | **NEW** | Buffer GraphQL poster (forked from Affiliate project) |
| `execution/autoresearch_loop.py` | **NEW** | Main loop orchestrator |
| `execution/threads_tracker_id.py` | **REUSE** | Trend signal input (from Obsidian AGENT) |
| `execution/editorial_checker.py` | **REUSE** | AI-ism + citation check (from Obsidian AGENT) |

## Reference Implementations

| Asset | Location | Reuse Strategy |
|:---|:---|:---|
| Buffer GraphQL posting | `Automatic Threads Affiliate/execution/post_to_threads.py` | Fork `create_post()` + thread metadata pattern |
| Buffer scheduling | `Reddit Threads Automation/execution/schedule_to_buffer.py` | Fork daily scheduling logic |
| Trend dork search | `Obsidian Writing/AGENT/execution/threads_tracker_id.py` | Copy + adapt for shadow analytics |
| Editorial checker | `Obsidian Writing/AGENT/execution/editorial_checker.py` | Copy as-is |
| Voice profile | `Obsidian Writing/AGENT/wiki/user_voice.md` | Seed data for voice_extractor.py |

## Environment Variables (`.env`)

```
GROQ_API_KEY=<from YT Automation>
BUFFER_ACCESS_TOKEN=<from Affiliate>
BUFFER_PROFILE_ID=<from Affiliate>
BUFFER_ORG_ID=<from Affiliate>
TAVILY_API_KEY=<from Obsidian AGENT>
THREADS_HANDLE=m.fauzan.aziz
MAX_VARIANTS_PER_DAY=10
POSTING_TIME=09:00
OBSIDIAN_RESEARCH_DIR=D:\Pribadi\Obsidian\Writing\Research
```

## Usage

```bash
# One-time voice extraction
python execution/voice_extractor.py

# Run daily loop (locally)
python execution/autoresearch_loop.py --topic Kenapa_Manusia_Takut_Sendiri

# Dry-run (no Buffer publish)
python execution/autoresearch_loop.py --topic Kenapa_Manusia_Takut_Sendiri --dry-run
```

## Learnings & Edge Cases

- Buffer free tier = 10 queued posts/channel. Thread = 1 post (multi-part). Queue frees on publish.
- Threads aggressively blocks Playwright scrapers. Tavily dork approach is more reliable for MVP.
- Groq rate limit: 30 req/min free tier. 10 calls/day is well within bounds.
- `editorial_checker.py` catches AI-isms post-mutation. Run as final validation gate.
