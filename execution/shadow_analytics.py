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
    Fetch analytics from Threads directly using Playwright.
    Returns a list of posts with engagement metrics.
    """
    from playwright.sync_api import sync_playwright
    import json
    import time
    
    posts = []
    
    with sync_playwright() as p:
        # Launch browser with stealth-like settings
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        captured_data = []

        def handle_response(response):
            # Capture GraphQL responses containing thread data
            if "graphql" in response.url and response.status == 200:
                try:
                    data = response.json()
                    if data and isinstance(data, dict):
                        # Look for profile feed data or media data
                        if "data" in data and ("mediaData" in data["data"] or "user" in data["data"]):
                            captured_data.append(data)
                except:
                    pass

        page.on("response", handle_response)
        
        url = f"https://www.threads.net/@{handle}"
        print(f"Fetching analytics from Threads profile {url}...")
        
        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            # Scroll to trigger more GraphQL loads
            page.mouse.wheel(0, 3000)
            time.sleep(3) # Wait for background requests
            
            for entry in captured_data:
                # Structure: data -> mediaData -> edges[] -> node -> thread_items[] -> post
                # OR structure: data -> user -> edge_user_media -> edges[] ...
                data_root = entry.get("data", {})
                
                # Check different possible data paths in the GraphQL response
                media_data = data_root.get("mediaData") or data_root.get("user", {}).get("edge_user_media")
                if not media_data:
                    continue
                    
                edges = media_data.get("edges", [])
                for edge in edges:
                    node = edge.get("node", {})
                    thread_items = node.get("thread_items", [])
                    
                    # If no thread_items, the node itself might be the post (depending on query)
                    if not thread_items and "post" in node:
                        thread_items = [{"post": node.get("post")}]
                    elif not thread_items and node.get("__typename") == "XDTGraphMedia":
                        thread_items = [{"post": node}]

                    for item in thread_items:
                        p_data = item.get("post")
                        if not p_data: continue
                        
                        pk = p_data.get("pk")
                        # Get text from caption or fragments
                        text = p_data.get("caption", {}).get("text", "")
                        if not text:
                            fragments = p_data.get("text_post_app_info", {}).get("text_fragments", {}).get("fragments", [])
                            text = " ".join(f.get("plaintext", "") for f in fragments if f.get("plaintext"))
                        
                        likes = p_data.get("like_count", 0)
                        
                        app_info = p_data.get("text_post_app_info", {})
                        replies = app_info.get("direct_reply_count", 0)
                        reposts = app_info.get("repost_count", 0)
                        quotes = app_info.get("quote_count", 0)
                        
                        post = {
                            "pk": str(pk),
                            "text": text[:200],
                            "likes": int(likes),
                            "replies": int(replies),
                            "reposts": int(reposts),
                            "quotes": int(quotes),
                        }
                        post["engagement"] = post["likes"] + post["replies"] + post["reposts"] + post["quotes"]
                        posts.append(post)
            
            # Deduplicate by pk
            seen = set()
            unique_posts = []
            for p in posts:
                if p["pk"] not in seen:
                    unique_posts.append(p)
                    seen.add(p["pk"])
            posts = unique_posts
            
            print(f"Retrieved {len(posts)} posts from Threads scraping.")
            return posts
            
        except Exception as e:
            print(f"Failed to fetch Threads analytics: {e}")
            return []
        finally:
            browser.close()


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
