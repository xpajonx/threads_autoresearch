import os
import sys
import json
import re
from pathlib import Path

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs

def parse_source_of_truth(topic_dir: Path):
    """
    Parses Source_of_Truth.md into discrete data points to format into short posts.
    """
    sot_path = topic_dir / "Source_of_Truth.md"
    if not sot_path.exists():
        raise FileNotFoundError(f"Missing {sot_path}")
        
    with open(sot_path, "r", encoding="utf-8") as f:
        content = f.read()

    data_points = []
    lines = content.split('\n')
    current_claim = ""
    current_evidence = ""
    
    for line in lines:
        if line.startswith("- **Klaim**:"):
            current_claim = line.replace("- **Klaim**:", "").strip()
        elif line.startswith("- **Bukti**:"):
            current_evidence = line.replace("- **Bukti**:", "").strip()
            
        if current_claim and current_evidence:
            data_points.append({
                "claim": current_claim,
                "evidence": current_evidence
            })
            current_claim = ""
            current_evidence = ""
            
    return data_points

def format_thread(topic_dir_name: str):
    print(f"Formatting thread for topic: {topic_dir_name}")
    topic_dir = configs.OBSIDIAN_RESEARCH_DIR / topic_dir_name
    
    data_points = parse_source_of_truth(topic_dir)
    
    thread_posts = []
    
    # 1. Hook Post (Placeholder to be mutated)
    thread_posts.append({
        "post_number": 1,
        "content": "[HOOK] Pernah nggak sih ngerasa takut banget sendirian? Ternyata ini bukan soal mental, tapi ada alasan ilmiahnya. A thread.",
    })
    
    # 2. Data Posts (Max 140 chars logic handled during mutation, but we set a baseline here)
    for i, dp in enumerate(data_points):
        # Merge claim and evidence into a short baseline representation
        base_text = f"{dp['claim']}"
        if len(base_text) > 135:
            base_text = base_text[:135] + "..."
            
        thread_posts.append({
            "post_number": i + 2,
            "content": base_text,
            "raw_evidence": dp['evidence'] # keep for the mutator to use
        })
        
    # 3. CTA Post
    thread_posts.append({
        "post_number": len(thread_posts) + 1,
        "content": "Kira-kira lo tipe yang butuh waktu sendiri, atau yang selalu butuh keramaian? Share di bawah ya! 👇",
    })
    
    out_path = configs.TMP_DIR / "thread_draft.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(thread_posts, f, indent=4)
        
    print(f"Formatted thread draft with {len(thread_posts)} posts to {out_path}")
    return out_path

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="Kenapa_Manusia_Takut_Sendiri")
    args = parser.parse_args()
    format_thread(args.topic)
