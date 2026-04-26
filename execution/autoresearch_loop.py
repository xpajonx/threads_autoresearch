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
from execution.drive_sync import DriveSync

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


def get_next_topic(drive: DriveSync = None) -> tuple[str | None, bool]:
    """
    Read topics_queue.json, sync with Research dir, return (topic, is_evergreen).
    is_evergreen is True if no new pending topics were found.
    """
    queue_name = "topics_queue.json"
    queue_path = configs.DATA_DIR / queue_name
    research_dir = configs.OBSIDIAN_RESEARCH_DIR
    
    # Sync queue from drive if provided
    if drive:
        queue_id = drive.find_file(queue_name, drive.output_folder_id)
        if queue_id:
            drive.download_file(queue_id, str(queue_path))

    if not research_dir.exists():
        print(f"Research dir not found: {research_dir}")
        return None, False

    # Load or init queue
    if queue_path.exists():
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "queue" not in data or not isinstance(data["queue"], list):
                print(f"Warning: {queue_path} invalid format. Resetting queue.")
                data = {"queue": []}
        except Exception as e:
            print(f"Error loading {queue_path}: {e}. Resetting.")
            data = {"queue": []}
    else:
        data = {"queue": []}

    # 1. Sync: Check for new folders in Research dir
    existing_topics = {item["topic"] for item in data["queue"] if isinstance(item, dict) and "topic" in item}
    found_new = False
    
    # Sync Dossier Folders (Only if local research dir exists, otherwise skip sync)
    if research_dir.exists():
        for d in sorted(research_dir.iterdir()):
            if not d.is_dir() or not (d / "Source_of_Truth.md").exists():
                continue
            if d.name == "AI_Insights" or d.name.startswith("."):
                continue
            if d.name not in existing_topics:
                print(f"New topic found in Research: {d.name}")
                data["queue"].append({"topic": d.name, "status": "pending", "date": None, "type": "dossier"})
                found_new = True

    if found_new:
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if drive:
            drive.upload_file(str(queue_path), drive.output_folder_id)

    # 2. Pick next pending
    for item in data["queue"]:
        if item["status"] == "pending":
            item["status"] = "processing"
            item["date"] = datetime.now().strftime("%Y-%m-%d")
            with open(queue_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if drive:
                drive.upload_file(str(queue_path), drive.output_folder_id)
            return item["topic"], False

    # 3. Evergreen Mode Fallback
    import random
    done_topics = [item for item in data["queue"] if item["status"] == "done"]
    if done_topics:
        chosen = random.choice(done_topics)
        print(f"Evergreen Mode: No new topics found. Re-processing: {chosen['topic']}")
        chosen["date"] = datetime.now().strftime("%Y-%m-%d")
        with open(queue_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if drive:
            drive.upload_file(str(queue_path), drive.output_folder_id)
        return chosen["topic"], True

    print("No topics found in queue or Research folder.")
    return None, False


def mark_topic_done(topic: str, drive: DriveSync = None):
    """Mark a topic as done in topics_queue.json."""
    queue_name = "topics_queue.json"
    queue_path = configs.DATA_DIR / queue_name
    if not queue_path.exists():
        return

    with open(queue_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data["queue"]:
        if item["topic"] == topic:
            item["status"] = "done"
            item["date"] = datetime.now().strftime("%Y-%m-%d")

    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    if drive:
        drive.upload_file(str(queue_path), drive.output_folder_id)


def main(topic: str, dry_run: bool = False, use_drive: bool = False):
    print(f"=== Autoresearch Loop: {topic} ===")
    
    drive = None
    if use_drive:
        print("Initializing Google Drive Sync...")
        drive = DriveSync()
        
        # Sync Inputs
        print(f"Syncing inputs for topic: {topic}...")
        # Since DriveSync.sync_inputs expects specific structure, we ensure local paths point to .tmp
        # We need a custom logic if Dossier is a folder
        # For now, sync_inputs looks for Source_of_Truth.md globally in input folder
        paths = drive.sync_inputs(topic)
        if not paths.get('sot'):
            print(f"[ERROR] Source_of_Truth.md not found in Drive for topic {topic}")
            return
        
        # Override config paths to use downloaded files in .tmp
        topic_path = configs.TMP_DIR 
    else:
        # Local logic
        if topic.startswith("FILE:"):
            file_rel_path = topic.replace("FILE:", "")
            topic_path = configs.OBSIDIAN_RESEARCH_DIR / file_rel_path
        else:
            topic_path = configs.OBSIDIAN_RESEARCH_DIR / topic

    voice_path = configs.EXECUTION_DIR / "voice_profile.json"
    if not voice_path.exists():
        print("voice_profile.json missing! Run voice_extractor.py first.")
        return

    data_points = parse_source_of_truth(topic_path)

    print(f"Data points found in Source_of_Truth: {len(data_points)}")
    if not data_points:
        print("  [ERROR] No data points found! Check if Source_of_Truth.md exists.")
        sys.exit(1)

    max_posts = min(configs.MAX_VARIANTS_PER_DAY, len(data_points))
    data_points = data_points[:max_posts]

    print(f"Generating: {max_posts} posts\n")

    # Load mutation memory for biased selection
    memory = load_mutation_memory()
    final_posts = []

    for i, dp in enumerate(data_points):
        post_id = f"post_{i+1}"
        mutation = select_mutation(memory)
        print(f"[{post_id}] mutation: {mutation}")

        mutated_text = mutate_single_post(dp, voice_path, mutation)
        if not mutated_text:
            log_result(post_id, 0.0, "failed", mutation)
            continue

        score, _ = score_virality([{"content": mutated_text}])
        print(f"  -> Score: {score} | '{mutated_text[:60]}...'")
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

    # Sync Outputs to Drive
    if use_drive:
        print("Syncing outputs to Google Drive...")
        results_tsv = configs.DATA_DIR / "results.tsv"
        drive.sync_outputs([str(final_path), str(results_tsv)])

    # Publish
    if not dry_run:
        print("\nPublishing to Buffer Queue...")
        for p in final_posts:
            try:
                publish_single_post(p["content"])
            except Exception as e:
                print(f"  [ERROR] Failed to publish {p['id']}: {e}")
    else:
        print("\n[DRY RUN] Skipping Buffer publish.")

    # Mark topic done
    mark_topic_done(topic, drive)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default=None, help="Folder name inside Research dir")
    parser.add_argument("--topic-auto", action="store_true", help="Auto-select next pending topic")
    parser.add_argument("--dry-run", action="store_true", help="Skip Buffer publishing")
    parser.add_argument("--use-drive", action="store_true", help="Use Google Drive for I/O")
    args = parser.parse_args()

    drive = DriveSync() if args.use_drive else None

    if args.topic_auto:
        topic, is_evergreen = get_next_topic(drive)
        if not topic:
            sys.exit(0)
        if is_evergreen:
            print("INFO: Entering Evergreen mode.")
    elif args.topic:
        topic = args.topic
    else:
        print("Provide --topic <name> or --topic-auto")
        sys.exit(1)

    main(topic, args.dry_run, args.use_drive)
