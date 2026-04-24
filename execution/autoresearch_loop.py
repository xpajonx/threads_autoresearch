"""
Autoresearch Loop: Generate 10 standalone posts per day.
Each post maps to 1 data point from Source_of_Truth.md,
with a unique mutation (biased by historical engagement).

Usage:
  python execution/autoresearch_loop.py --topic Kenapa_Manusia_Takut_Sendiri
  python execution/autoresearch_loop.py --topic-auto   # picks next pending topic
  python execution/autoresearch_loop.py --topic X --dry-run
"""
import os
import sys
import json
import re
from datetime import datetime
from pathlib import Path

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs
from execution.thread_formatter import parse_source_of_truth
from execution.virality_scorer import score_virality
from execution.style_mutator import mutate_single_post, select_mutation, load_mutation_memory
from execution.buffer_publisher import publish_single_post


def log_result(post_id, score, status, mutation, content=""):
    """Append a row to results.tsv."""
    tsv_path = configs.DATA_DIR / "results.tsv"
    if not tsv_path.exists():
        with open(tsv_path, "w", encoding="utf-8") as f:
            f.write("post_id\tscore\tstatus\tmutation\tcontent\tdate\n")

    mut_str = json.dumps(mutation)
    date_str = datetime.now().strftime("%Y-%m-%d")
    # Sanitize content for TSV (remove tabs/newlines)
    safe_content = content.replace("\t", " ").replace("\n", " ")[:120]
    with open(tsv_path, "a", encoding="utf-8") as f:
        f.write(f"{post_id}\t{score}\t{status}\t{mut_str}\t{safe_content}\t{date_str}\n")


def get_next_topic() -> tuple[str | None, bool]:
    """
    Read topics_queue.json, sync with Research dir, return (topic, is_evergreen).
    is_evergreen is True if no new pending topics were found.
    """
    queue_path = configs.DATA_DIR / "topics_queue.json"
    research_dir = configs.OBSIDIAN_RESEARCH_DIR
    
    if not research_dir.exists():
        print(f"Research dir not found: {research_dir}")
        return None, False

    # Load or init queue
    if queue_path.exists():
        with open(queue_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"queue": []}

    # 1. Sync: Check for new folders in Research dir
    existing_topics = {item["topic"] for item in data["queue"]}
    found_new = False
    
    # Sync Dossier Folders
    for d in sorted(research_dir.iterdir()):
        if not d.is_dir() or not (d / "Source_of_Truth.md").exists():
            continue
        if d.name == "AI_Insights" or d.name.startswith("."):
            continue
        if d.name not in existing_topics:
            print(f"New topic found in Research: {d.name}")
            data["queue"].append({"topic": d.name, "status": "pending", "date": None, "type": "dossier"})
            found_new = True

    # Sync AI_Insights Files
    insights_dir = research_dir / "AI_Insights"
    if insights_dir.exists():
        for f in sorted(insights_dir.glob("*.md")):
            topic_id = f"FILE:AI_Insights/{f.name}"
            if topic_id not in existing_topics:
                # Check if it's already published by checking content
                with open(f, "r", encoding="utf-8") as file_content:
                    if "status: published" in file_content.read().lower():
                        continue
                print(f"New AI Insight found: {f.name}")
                data["queue"].append({"topic": topic_id, "status": "pending", "date": None, "type": "insight"})
                found_new = True

    if found_new:
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # 2. Pick next pending
    for item in data["queue"]:
        if item["status"] == "pending":
            item["status"] = "processing"
            item["date"] = datetime.now().strftime("%Y-%m-%d")
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return item["topic"], False

    # 3. Evergreen Mode Fallback
    import random
    done_topics = [item for item in data["queue"] if item["status"] == "done"]
    if done_topics:
        chosen = random.choice(done_topics)
        print(f"Evergreen Mode: No new topics found. Re-processing: {chosen['topic']}")
        chosen["date"] = datetime.now().strftime("%Y-%m-%d")
        # Do NOT set status to processing for evergreen, keep it done or temporary
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return chosen["topic"], True

    print("No topics found in queue or Research folder.")
    return None, False


def mark_topic_done(topic: str):
    """Mark a topic as done in topics_queue.json and update file status if applicable."""
    queue_path = configs.DATA_DIR / "topics_queue.json"
    if not queue_path.exists():
        return

    with open(queue_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data["queue"]:
        if item["topic"] == topic:
            item["status"] = "done"
            item["date"] = datetime.now().strftime("%Y-%m-%d")
            
            # If it's an AI Insight file, update the file content too
            if topic.startswith("FILE:"):
                file_rel_path = topic.replace("FILE:", "")
                file_path = configs.OBSIDIAN_RESEARCH_DIR / file_rel_path
                if file_path.exists():
                    try:
                        with open(file_path, "r", encoding="utf-8") as f_meta:
                            content = f_meta.read()
                        new_content = re.sub(r"status:\s*pending", "status: published", content, flags=re.IGNORECASE)
                        if new_content == content and "status:" not in content.lower():
                            # If no status line exists, append it
                            new_content = content.strip() + "\n\nstatus: published"
                        
                        with open(file_path, "w", encoding="utf-8") as f_meta:
                            f_meta.write(new_content)
                        print(f"Updated file status to published: {file_path.name}")
                    except Exception as e:
                        print(f"Failed to update file status for {file_path}: {e}")

    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main(topic: str, dry_run: bool = False):
    print(f"=== Autoresearch Loop: {topic} ===")

    voice_path = configs.EXECUTION_DIR / "voice_profile.json"
    if not voice_path.exists():
        print("voice_profile.json missing! Run voice_extractor.py first.")
        return

    # Handle file-based topics (AI Insights) vs Folder-based (Dossiers)
    if topic.startswith("FILE:"):
        file_rel_path = topic.replace("FILE:", "")
        topic_path = configs.OBSIDIAN_RESEARCH_DIR / file_rel_path
    else:
        topic_path = configs.OBSIDIAN_RESEARCH_DIR / topic
        
    data_points = parse_source_of_truth(topic_path)

    print(f"Data points found in Source_of_Truth: {len(data_points)}")
    if not data_points:
        print("  [ERROR] No data points found! Check if Source_of_Truth.md follows the '- **Klaim**: ...' format.")
        sys.exit(1)

    max_posts = min(configs.MAX_VARIANTS_PER_DAY, len(data_points))
    data_points = data_points[:max_posts]

    print(f"Generating: {max_posts} posts\n")

    # Load mutation memory for biased selection
    memory = load_mutation_memory()
    if memory:
        print(f"Mutation memory loaded: {len(memory)} tags tracked.")
    else:
        print("No mutation memory yet. Using pure exploration.")

    final_posts = []

    for i, dp in enumerate(data_points):
        post_id = f"post_{i+1}"

        # Epsilon-greedy mutation selection
        mutation = select_mutation(memory)
        mode = "exploit" if memory and any(m.get("total", 0) > 0 for m in memory.values()) else "explore"
        print(f"[{post_id}] {mode} | mutation: {mutation}")

        mutated_text = mutate_single_post(dp, voice_path, mutation)

        if not mutated_text:
            print(f"  FAILED to generate.")
            log_result(post_id, 0.0, "failed", mutation)
            continue

        # Deterministic pre-publish score
        score, breakdown = score_virality([{"content": mutated_text}])

        print(f"  -> Score: {score} | Len: {len(mutated_text)} | '{mutated_text[:60]}...'")
        log_result(post_id, score, "generated", mutation, mutated_text)

        final_posts.append({
            "id": post_id,
            "content": mutated_text,
            "mutation": mutation,
            "score": score,
        })

    # Save
    final_path = configs.TMP_DIR / "final_posts.json"
    with open(final_path, "w", encoding="utf-8") as f:
        json.dump(final_posts, f, indent=4, ensure_ascii=False)

    print(f"\n=== Saved {len(final_posts)} posts to {final_path} ===")

    # Publish
    publish_success_count = 0
    if not dry_run:
        print("\nPublishing to Buffer Queue...")
        for p in final_posts:
            try:
                publish_single_post(p["content"])
                publish_success_count += 1
            except Exception as e:
                print(f"  [ERROR] Failed to publish {p['id']}: {e}")
    else:
        print("\n[DRY RUN] Skipping Buffer publish.")
        publish_success_count = len(final_posts)

    if publish_success_count == 0 and len(data_points) > 0:
        print("\n[CRITICAL ERROR] A topic was selected but 0 posts were successfully published.")
        sys.exit(1)

    # Mark topic done
    mark_topic_done(topic)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default=None, help="Folder name inside Research dir")
    parser.add_argument("--topic-auto", action="store_true", help="Auto-select next pending topic")
    parser.add_argument("--dry-run", action="store_true", help="Skip Buffer publishing")
    args = parser.parse_args()

    if args.topic_auto:
        topic, is_evergreen = get_next_topic()
        if not topic:
            sys.exit(0) # Exit cleanly if nothing to do
        if is_evergreen:
            print("INFO: Entering Evergreen mode (re-processing old topic).")
    elif args.topic:
        topic = args.topic
    else:
        print("Provide --topic <name> or --topic-auto")
        sys.exit(1)

    main(topic, args.dry_run)
