import sys
import json
import os
import re
from pathlib import Path
from difflib import SequenceMatcher
from apify_client import ApifyClient

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs
from execution.drive_sync import DriveSync

def get_threads_analytics_via_apify(handle: str) -> list[dict]:
    """
    Search Threads profile via Apify (george.the.developer/threads-scraper).
    """
    if not configs.APIFY_API_TOKEN:
        print("APIFY_API_TOKEN missing.")
        return []

    print(f"Fetching analytics for @{handle} via Apify...")
    client = ApifyClient(configs.APIFY_API_TOKEN)
    
    # Profile format
    run_input = {
        "usernames": [handle],
        "maxPosts": 50,
        "includeReplies": False
    }

    try:
        # Run the Actor and wait for it to finish
        run = client.actor("george.the.developer/threads-scraper").call(run_input=run_input)
        
        results = []
        # Fetch results from the run's dataset
        for item in client.dataset(run['defaultDatasetId']).iterate_items():
            # Actor uses 'type' to distinguish 'profile' and 'post'
            if item.get("type") != "post":
                continue

            text = item.get("postText", "")
            likes = int(item.get("likeCount", 0))
            replies = int(item.get("replyCount", 0))
            reposts = int(item.get("repostCount", 0))
            
            post = {
                "pk": str(item.get("id", item.get("postUrl", ""))),
                "text": text[:200],
                "likes": likes,
                "replies": replies,
                "reposts": reposts,
                "quotes": 0, # Not provided by this actor
                "views": 0,  # Not provided by this actor
            }
            post["engagement"] = likes + replies + reposts
            results.append(post)
                
        print(f"Retrieved {len(results)} posts from Apify.")
        for i, p in enumerate(results[:5]):
            print(f"  Scraped {i}: '{p['text']}' (E={p['engagement']})")
        return results

    except Exception as e:
        print(f"Apify pipeline failed: {e}")
        return []

def scrape_threads_profile(handle: str = None) -> list[dict]:
    """
    Tries to get analytics from Apify.
    """
    handle = handle or configs.THREADS_HANDLE or "m.fauzan.aziz"
    return get_threads_analytics_via_apify(handle)

def fuzzy_match(text_a: str, text_b: str, threshold: float = 0.6) -> float:
    a = text_a.lower().replace("\\n", " ").replace("\\\\n", " ").strip()
    b = text_b.lower().replace("\\n", " ").replace("\\\\n", " ").strip()
    return SequenceMatcher(None, a, b).ratio()

def load_results_tsv() -> list[dict]:
    tsv_path = configs.DATA_DIR / "results.tsv"
    if not tsv_path.exists(): return []
    rows = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        header = f.readline().strip().split("\t")
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= len(header):
                rows.append(dict(zip(header, parts)))
    return rows

def save_results_tsv(rows: list[dict]):
    tsv_path = configs.DATA_DIR / "results.tsv"
    if not rows: return
    header = list(rows[0].keys())
    with open(tsv_path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for row in rows:
            f.write("\t".join(str(row.get(h, "")) for h in header) + "\n")

def load_mutation_memory() -> dict:
    mem_path = configs.DATA_DIR / "mutation_memory.json"
    if mem_path.exists():
        with open(mem_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_mutation_memory(memory: dict):
    mem_path = configs.DATA_DIR / "mutation_memory.json"
    with open(mem_path, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def update_memory_from_engagement(scraped_posts: list[dict], results: list[dict], memory: dict):
    if not scraped_posts or not results:
        print("No data to match.")
        return memory, results
    engagements = [p["engagement"] for p in scraped_posts]
    median_eng = sorted(engagements)[len(engagements) // 2] if engagements else 0
    print(f"Median engagement: {median_eng}")
    from datetime import datetime
    today = datetime.now().date()
    matched = 0
    
    # Store indices of rows to keep to allow dropping unmatched old rows
    rows_to_keep = []
    
    for i, result in enumerate(results):
        if result.get("status") == "feedback_done":
            rows_to_keep.append(i)
            continue
            
        post_date_str = result.get("date", "")
        is_too_recent = False
        is_too_old = False
        if post_date_str:
            try:
                post_date = datetime.strptime(post_date_str, "%Y-%m-%d").date()
                age_days = (today - post_date).days
                if age_days < 2: 
                    is_too_recent = True
                elif age_days > 7:
                    is_too_old = True
            except: pass
            
        if is_too_recent:
            print(f"  Skipping '{result.get('content', '')[:30]}...' (too recent: {post_date_str})")
            rows_to_keep.append(i)
            continue
            
        post_content = result.get("content", "")
        if not post_content:
            rows_to_keep.append(i)
            continue
            
        best_match, best_ratio = None, 0.0
        for sp in scraped_posts:
            ratio = fuzzy_match(post_content, sp["text"])
            if ratio > best_ratio:
                best_ratio, best_match = ratio, sp
                
        if best_match and best_ratio > 0.5:
            matched += 1
            eng = best_match["engagement"]
            is_win = eng > median_eng
            mutation = json.loads(result.get("mutation", "{}"))
            for k, v in mutation.items():
                tag = f"{k}:{v}"
                if tag not in memory:
                    memory[tag] = {"wins": 0, "total": 0, "total_engagement": 0}
                memory[tag]["total"] += 1
                memory[tag]["total_engagement"] += eng
                if is_win: memory[tag]["wins"] += 1
            result["status"] = "feedback_done"
            print(f"  Matched '{post_content[:50]}...' -> engagement={eng} (win={is_win})")
            rows_to_keep.append(i)
        else:
            if is_too_old:
                print(f"  Deleting unmatched old post '{post_content[:30]}...' (age > 7 days)")
                # We do NOT append to rows_to_keep, effectively deleting it
            else:
                print(f"  No match for '{post_content[:30]}...' (best ratio: {best_ratio:.2f})")
                rows_to_keep.append(i)

    # Filter results to only keep valid/matched or recent rows
    updated_results = [results[i] for i in rows_to_keep]
    print(f"\nMatched {matched} posts to analytics. Removed {len(results) - len(updated_results)} unmatched old posts.")
    return memory, updated_results

def run_feedback(use_drive: bool = False):
    handle = configs.THREADS_HANDLE or "m.fauzan.aziz"
    drive = None
    if use_drive:
        drive = DriveSync()
        for f in ["results.tsv", "mutation_memory.json"]:
            fid = drive.find_file(f, drive.output_folder_id)
            if fid: drive.download_file(fid, str(configs.DATA_DIR / f))
    scraped = scrape_threads_profile(handle)
    if not scraped:
        print("No data. Exiting.")
        return
    results = load_results_tsv()
    memory = load_mutation_memory()
    memory, results = update_memory_from_engagement(scraped, results, memory)
    save_mutation_memory(memory)
    save_results_tsv(results)
    if use_drive:
        drive.sync_outputs([
            str(configs.DATA_DIR / "results.tsv"),
            str(configs.DATA_DIR / "mutation_memory.json")
        ])

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback", action="store_true")
    parser.add_argument("--use-drive", action="store_true")
    args = parser.parse_args()
    if args.feedback:
        run_feedback(args.use_drive)
    else:
        posts = scrape_threads_profile()
        for p in posts:
            print(f"{p['text'][:60]}... | E={p['engagement']}")
