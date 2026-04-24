"""
Shadow Analytics: Scrape Threads profile for engagement data,
match to posted content, and update mutation_memory.json.

Uses Scrapling (free, self-hosted) to extract post metrics
directly from embedded SSR JSON in the Threads profile page.
"""
import sys
import os
import re
import json
from pathlib import Path
from difflib import SequenceMatcher

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs


def scrape_threads_profile(handle: str) -> list[dict]:
    """
    Fetch analytics from Buffer API instead of scraping Threads directly.
    Returns a list of posts with engagement metrics.
    """
    import requests
    
    token = configs.BUFFER_ACCESS_TOKEN
    profile_id = configs.BUFFER_PROFILE_ID
    
    if not token or not profile_id:
        print("Buffer credentials missing. Cannot fetch analytics.")
        return []

    url = f"https://api.bufferapp.com/1/profiles/{profile_id}/updates/sent.json"
    params = {
        "access_token": token,
        "count": 100 # Get last 100 posts
    }

    print(f"Fetching analytics from Buffer API for profile {profile_id}...")
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        updates = data.get("updates", [])
        posts = []
        
        for up in updates:
            stats = up.get("statistics", {})
            # Normalized stats for Threads/Buffer
            likes = stats.get("favorites", 0) or stats.get("likes", 0)
            replies = stats.get("replies", 0)
            reposts = stats.get("retweets", 0) or stats.get("reposts", 0)
            quotes = stats.get("quotes", 0)
            
            post = {
                "pk": up.get("id"),
                "text": up.get("text", "")[:200],
                "likes": int(likes),
                "replies": int(replies),
                "reposts": int(reposts),
                "quotes": int(quotes),
            }
            post["engagement"] = post["likes"] + post["replies"] + post["reposts"] + post["quotes"]
            posts.append(post)
            
        print(f"Retrieved {len(posts)} posts from Buffer analytics.")
        return posts
        
    except Exception as e:
        print(f"Failed to fetch Buffer analytics: {e}")
        return []


def fuzzy_match(text_a: str, text_b: str, threshold: float = 0.6) -> float:
    """Return similarity ratio between two strings."""
    # Normalize: lowercase, strip escaped chars
    a = text_a.lower().replace("\\n", " ").replace("\\\\n", " ").strip()
    b = text_b.lower().replace("\\n", " ").replace("\\\\n", " ").strip()
    return SequenceMatcher(None, a, b).ratio()


def load_results_tsv() -> list[dict]:
    """Load results.tsv into a list of dicts."""
    tsv_path = configs.DATA_DIR / "results.tsv"
    if not tsv_path.exists():
        return []

    rows = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= len(header):
                row = dict(zip(header, parts))
                rows.append(row)
    return rows


def save_results_tsv(rows: list[dict]):
    """Save the updated results list back to results.tsv."""
    tsv_path = configs.DATA_DIR / "results.tsv"
    if not rows:
        return
    
    header = list(rows[0].keys())
    with open(tsv_path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for row in rows:
            f.write("\t".join(str(row.get(h, "")) for h in header) + "\n")


def load_mutation_memory() -> dict:
    """Load or initialize mutation_memory.json."""
    mem_path = configs.DATA_DIR / "mutation_memory.json"
    if mem_path.exists():
        with open(mem_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_mutation_memory(memory: dict):
    """Save mutation_memory.json."""
    mem_path = configs.DATA_DIR / "mutation_memory.json"
    with open(mem_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)


def update_memory_from_engagement(scraped_posts: list[dict], results: list[dict], memory: dict):
    """
    Match scraped posts to results.tsv entries with Maturity Delay (H-2).
    If engagement > median, count as a 'win' for that mutation.
    """
    if not scraped_posts or not results:
        print("No data to match.")
        return memory

    # Calculate median engagement
    engagements = [p["engagement"] for p in scraped_posts]
    median_eng = sorted(engagements)[len(engagements) // 2] if engagements else 0
    print(f"Median engagement: {median_eng}")

    from datetime import datetime
    today = datetime.now().date()
    
    matched = 0
    for result in results:
        if result.get("status") == "feedback_done":
            continue

        # Maturity Delay: Only evaluate posts that are at least 2 days old (H-2)
        # This ensures the engagement has "settled" equally for morning vs night posts.
        post_date_str = result.get("date", "")
        if post_date_str:
            try:
                post_date = datetime.strptime(post_date_str, "%Y-%m-%d").date()
                days_old = (today - post_date).days
                if days_old < 2:
                    continue  # Skip, too young to evaluate
            except ValueError:
                pass

        mutation_str = result.get("mutation", "{}")

        try:
            mutation = json.loads(mutation_str)
        except json.JSONDecodeError:
            continue

        # Try to match via final_posts.json (has the actual content)
        # Wait, final_posts.json only has the *latest* generation batch.
        # We should match directly against result['content'] which we now save in results.tsv!
        post_content = result.get("content", "")
        if not post_content:
            continue
            
        # Fuzzy match against scraped posts
        best_match = None
        best_ratio = 0.0
        for sp in scraped_posts:
            ratio = fuzzy_match(post_content, sp["text"])
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = sp

        if best_match and best_ratio > 0.5:
            matched += 1
            eng = best_match["engagement"]
            is_win = eng > median_eng

            # Update memory for each mutation key-value
            for key, val in mutation.items():
                tag = f"{key}:{val}"
                if tag not in memory:
                    memory[tag] = {"wins": 0, "total": 0, "total_engagement": 0}
                memory[tag]["total"] += 1
                memory[tag]["total_engagement"] += eng
                if is_win:
                    memory[tag]["wins"] += 1

            # Mark as done so we don't evaluate it again tomorrow
            result["status"] = "feedback_done"
            print(f"  Matched '{post_content[:50]}...' -> engagement={eng} (win={is_win})")

    print(f"\nMatched {matched} posts to scraped analytics.")
    return memory


def run_feedback():
    """Main feedback loop: scrape -> match -> update memory."""
    handle = configs.THREADS_HANDLE or "m.fauzan.aziz"

    # 1. Scrape
    scraped = scrape_threads_profile(handle)
    if not scraped:
        print("No scraped data. Exiting.")
        return

    # Save analytics
    out_path = configs.TMP_DIR / "threads_analytics.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scraped, f, indent=2, ensure_ascii=False)
    print(f"Saved analytics to {out_path}")

    # 2. Load results
    results = load_results_tsv()

    # 3. Load memory
    memory = load_mutation_memory()

    # 4. Update
    memory = update_memory_from_engagement(scraped, results, memory)

    # 5. Save
    save_mutation_memory(memory)
    save_results_tsv(results)
    print(f"\nMutation memory updated. {len(memory)} mutation tags tracked.")

    # 6. Print leaderboard
    if memory:
        print("\n=== Mutation Leaderboard ===")
        sorted_tags = sorted(memory.items(), key=lambda x: x[1]["wins"] / max(x[1]["total"], 1), reverse=True)
        for tag, stats in sorted_tags:
            win_rate = stats["wins"] / max(stats["total"], 1)
            avg_eng = stats["total_engagement"] / max(stats["total"], 1)
            print(f"  {tag}: {stats['wins']}/{stats['total']} wins ({win_rate:.0%}) | avg engagement: {avg_eng:.1f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback", action="store_true", help="Run the feedback loop")
    args = parser.parse_args()

    if args.feedback:
        run_feedback()
    else:
        # Just scrape and print
        handle = configs.THREADS_HANDLE or "m.fauzan.aziz"
        posts = scrape_threads_profile(handle)
        for p in posts:
            print(f"{p['text'][:60]}... | E={p['engagement']}")
