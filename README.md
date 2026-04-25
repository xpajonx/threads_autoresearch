# Threads Autoresearch: Technical Workflow & Architecture

Systematic autonomous content engine for Threads. Uses a 3-layer architecture (Directive, Orchestration, Execution) to automate research-to-publish loop with adaptive style mutations based on real engagement data.

## 🏗️ 3-Layer Architecture

### Layer 1: Directive (Strategy)
Defined in `viral_thread_autoresearch_pipeline.md`. SOP for how topics are selected, mutated, and verified.

### Layer 2: Orchestration (Decision Making)
Handled by `execution/autoresearch_loop.py`. Manages the high-level flow:
- Syncs Obsidian research folders to `topics_queue.json`.
- Picks next pending topic.
- Biases generation based on `mutation_memory.json`.
- Coordinates generation, scoring, and publishing.

### Layer 3: Execution (Deterministic Tools)
Specialized Python scripts in `execution/`:
- `voice_extractor.py`: Creates `voice_profile.json` from sample content.
- `thread_formatter.py`: Parses `Source_of_Truth.md` into atomic data points.
- `style_mutator.py`: Uses Groq (Llama 3.3 70B) with CRIBS-style mutations (Epsilon-greedy selection).
- `virality_scorer.py`: Pre-publish deterministic evaluation of generated content.
- `buffer_publisher.py`: Legacy Buffer GraphQL integration.
- `shadow_analytics.py`: **Playwright-based scraper** to fetch real Threads engagement (bypass API blocks).

---

## 🔄 The Data Lifecycle

### 1. Topic Ingestion
- Folders in `D:\Pribadi\Obsidian\Writing\Research` containing `Source_of_Truth.md` are auto-detected.
- Topics are queued in `topics_queue.json`.

### 2. Autonomous Generation (`autoresearch_loop.py`)
- **Parser**: Extracts "Klaim" and "Bukti" pairs from the markdown dossier.
- **Mutation Selector**: Loads `mutation_memory.json`. Uses 30% exploration (random) vs 70% exploitation (top-performing) to select CRIBS parameters (Hook type, Vocab register, etc.).
- **Generator**: Groq LLM writes conversational Indonesian posts strictly <500 chars using the `voice_profile.json`.
- **Scorer**: `virality_scorer.py` gives a heuristic score (0-100) based on readability, hook strength, and value density.

### 3. Publishing
- Validated posts are sent to the Buffer queue for scheduling (09:00 WIB cadence).

### 4. Feedback Loop (`shadow_analytics.py`)
- **Scraper**: Playwright launches headless Chromium, navigates to profile, and intercepts GraphQL responses (`XDTUserTextPostsResponseEdge`).
- **Matcher**: Matches scraped engagement stats (`like_count`, `reply_count`, etc.) to local records in `results.tsv` using fuzzy string matching.
- **Learner**: Updates `mutation_memory.json`. If a post's engagement > median, it's a "win". Mutation tags (e.g., `hook_type:curiosity_gap`) get updated win rates.

---

## 🛠️ Key Files & Config
- **`.env`**: API keys (Groq, Tavily) and handles.
- **`execution/config.py`**: Central path and environment management.
- **`AI_Automation_Data/`**: Persistent state (not committed).
  - `results.tsv`: Historical log of all generated content and metrics.
  - `mutation_memory.json`: The "brain" of the engine.
  - `topics_queue.json`: Status of all research dossiers.

## 🚀 Usage
```bash
# Extract voice from existing content
python execution/voice_extractor.py

# Run the generation loop for the next pending topic
python execution/autoresearch_loop.py --topic-auto

# Scrape engagement and update mutation memory
python execution/shadow_analytics.py --feedback
```
