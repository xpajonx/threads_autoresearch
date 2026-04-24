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
    Supports variations in formatting (spaces, bolding, bullet types).
    """
    sot_path = topic_dir / "Source_of_Truth.md"
    if not sot_path.exists():
        raise FileNotFoundError(f"Missing {sot_path}")
        
    with open(sot_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex to find Klaim and Bukti pairs more flexibly
    # Matches: - **Klaim**: text, * **Klaim**: text, Klaim: text, etc.
    claim_pattern = re.compile(r"(?:^|\n)[ \t]*[-*+]?[ \t]*\**Klaim\**\s*:\s*(.*)", re.IGNORECASE)
    evidence_pattern = re.compile(r"(?:^|\n)[ \t]*[-*+]?[ \t]*\**Bukti\**\s*:\s*(.*)", re.IGNORECASE)

    data_points = []
    
    # Split content by Klaim to find blocks
    # This assumes each data point starts with a Klaim
    blocks = re.split(r"(?=\n[ \t]*[-*+]?[ \t]*\**Klaim\**\s*:)", "\n" + content, flags=re.IGNORECASE)
    
    for block in blocks:
        if not block.strip():
            continue
            
        claim_match = claim_pattern.search(block)
        evidence_match = evidence_pattern.search(block)
        
        if claim_match and evidence_match:
            data_points.append({
                "claim": claim_match.group(1).strip(),
                "evidence": evidence_match.group(1).strip()
            })
            
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
