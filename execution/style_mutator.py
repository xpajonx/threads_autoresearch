"""
Style Mutator: generates a single standalone post from a data point
using Groq LLM, with CRIBS-style mutations biased by mutation_memory.json.
"""
import sys
import os
import json
import random
import requests
from pathlib import Path

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs

CRIBS_PARAMS = {
    "hook_type": ["curiosity_gap", "pattern_interrupt", "contrarian", "statistic_bomb", "personal_anecdote"],
    "vocab_register": ["street", "balanced", "formal"],
    "rhythm": ["staccato", "flowing", "mixed"],
    "data_density": ["low", "medium", "high"],
    "emotional_arc": ["tension_release", "escalating", "bookend"],
}

EPSILON = 0.3  # 30% explore, 70% exploit


def load_mutation_memory() -> dict:
    """Load mutation_memory.json."""
    mem_path = configs.DATA_DIR / "mutation_memory.json"
    if mem_path.exists():
        with open(mem_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def generate_random_mutation() -> dict:
    """Pure random mutation (exploration)."""
    num_mutations = random.choice([1, 2])
    keys = random.sample(list(CRIBS_PARAMS.keys()), num_mutations)
    return {k: random.choice(CRIBS_PARAMS[k]) for k in keys}


def generate_biased_mutation(memory: dict) -> dict:
    """Exploitation: pick mutations with highest win rate from memory."""
    if not memory or not isinstance(memory, dict):
        return generate_random_mutation()

    # Score each mutation tag by win rate
    scored = {}
    for tag, stats in memory.items():
        if isinstance(stats, dict) and stats.get("total", 0) > 0:
            scored[tag] = stats["wins"] / stats["total"]

    if not scored:
        return generate_random_mutation()

    # Sort by win rate, pick top tags
    sorted_tags = sorted(scored.items(), key=lambda x: x[1], reverse=True)

    mutation = {}
    used_keys = set()

    for tag, rate in sorted_tags[:2]:  # Pick top 2 winning mutations
        key, val = tag.split(":", 1)
        if key in CRIBS_PARAMS and key not in used_keys:
            mutation[key] = val
            used_keys.add(key)

    # If we couldn't fill from memory, add a random one
    if not mutation:
        return generate_random_mutation()

    return mutation


def select_mutation(memory: dict = None, epsilon: float = EPSILON) -> dict:
    """
    Epsilon-greedy mutation selection.
    - With probability epsilon: explore (random mutation)
    - With probability 1-epsilon: exploit (best-performing mutation from memory)
    """
    if memory is None:
        memory = load_mutation_memory()

    if not isinstance(memory, dict):
        return generate_random_mutation()

    if random.random() < epsilon or not memory:
        return generate_random_mutation()
    else:
        return generate_biased_mutation(memory)


def call_groq_api(prompt: str) -> str:
    """Call Groq API with a single prompt."""
    if not configs.GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {configs.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
        "response_format": {"type": "json_object"},
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()

    return response.json()["choices"][0]["message"]["content"]


def mutate_single_post(data_point: dict, voice_path: Path, mutation: dict) -> str | None:
    """Generate a single standalone post from a data point with mutation applied."""
    with open(voice_path, "r", encoding="utf-8") as f:
        voice = json.load(f)

    voice_str = json.dumps(voice, indent=2)
    mutation_str = json.dumps(mutation, indent=2)

    prompt = f"""
You are a viral Threads ghostwriter for {voice.get('threads_handle')}.
You must write a SINGLE standalone post based on the following data point.

VOICE CONSTRAINTS:
{voice_str}

STYLE MUTATIONS TO APPLY:
{mutation_str}

STRICT PLATFORM RULES:
1. Return ONLY a valid JSON object with a single key "post" containing a string.
2. The post should be detailed but MUST be strictly UNDER 500 characters. No exceptions.
3. Do not use AI-isms (like 'essentially', 'in conclusion').
4. Do not include hashtags.
5. Combine the claim and evidence naturally.

DATA POINT TO CONVEY:
Claim: {data_point.get('claim')}
Evidence: {data_point.get('evidence')}

Return JSON output only:
"""

    try:
        response_text = call_groq_api(prompt)
        result_json = json.loads(response_text)
        return result_json.get("post", "").strip()
    except Exception as e:
        print(f"Failed to generate post: {e}")
        return None
