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
    Versatile Parser for both Research Dossiers and AI Insights.
    1. Tries Klaim/Bukti pairs (structured).
    2. Tries ### Headers (semi-structured).
    3. Tries Paragraph blocks (unstructured).
    """
    sot_path = topic_dir / "Source_of_Truth.md"
    # If it's a direct file path (for insights), use it directly
    if not sot_path.exists() and topic_dir.is_file():
        sot_path = topic_dir
    
    if not sot_path.exists():
        raise FileNotFoundError(f"Missing Source of Truth at {sot_path}")
        
    with open(sot_path, "r", encoding="utf-8") as f:
        content = f.read()

    data_points = []
    
    # --- Strategy 1: Klaim/Bukti pairs ---
    lines = content.splitlines()
    current_claim = ""
    current_evidence = ""
    for line in lines:
        line_clean = line.strip()
        if not line_clean: continue
        if re.search(r"Klaim", line_clean, re.IGNORECASE) and (":" in line_clean or "**" in line_clean):
            parts = re.split(r"Klaim\**\s*[:\-]?\s*", line_clean, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) > 1: current_claim = parts[1].strip()
        elif re.search(r"Bukti", line_clean, re.IGNORECASE) and (":" in line_clean or "**" in line_clean):
            parts = re.split(r"Bukti\**\s*[:\-]?\s*", line_clean, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) > 1: current_evidence = parts[1].strip()
        if current_claim and current_evidence:
            data_points.append({"claim": current_claim, "evidence": current_evidence})
            current_claim = ""; current_evidence = ""

    # --- Strategy 2: Fallback to Headers (###) ---
    if not data_points:
        sections = re.split(r"(?=\n### )", "\n" + content)
        for section in sections:
            section = section.strip()
            if not section.startswith("###"): continue
            slines = section.splitlines()
            claim = re.sub(r"^###\s*", "", slines[0]).strip()
            claim = re.sub(r"^\d+\.\s*", "", claim)
            evidence = " ".join([l.strip() for l in slines[1:] if l.strip()])
            if claim and evidence:
                data_points.append({"claim": claim, "evidence": evidence[:500]})

    # --- Strategy 3: Fallback to Paragraph Blocks (for simple notes/insights) ---
    if not data_points:
        # Split by double newlines, treat each non-empty block as a potential post
        blocks = [b.strip() for b in content.split("\n\n") if len(b.strip()) > 40]
        for block in blocks:
            # Skip title and metadata
            if block.startswith("#") or "status:" in block.lower(): continue
            # Use first sentence as claim, rest as evidence
            parts = re.split(r"(?<=[.!?])\s+", block, maxsplit=1)
            if len(parts) > 1:
                data_points.append({"claim": parts[0], "evidence": parts[1][:500]})
            else:
                data_points.append({"claim": "Insight", "evidence": block[:500]})

    return data_points

def format_thread(topic_dir_name: str):
    topic_dir = configs.OBSIDIAN_RESEARCH_DIR / topic_dir_name
    data_points = parse_source_of_truth(topic_dir)
    
    thread_posts = []
    thread_posts.append({
        "post_number": 1,
        "content": f"[HOOK] Update terbaru soal {topic_dir_name.replace('_', ' ')}. A thread.",
    })
    
    for i, dp in enumerate(data_points):
        thread_posts.append({
            "post_number": i + 2,
            "content": dp['claim'],
            "raw_evidence": dp['evidence']
        })
        
    thread_posts.append({
        "post_number": len(thread_posts) + 1,
        "content": "Gimana menurut lo? Ada perspektif lain? 👇",
    })
    
    out_path = configs.TMP_DIR / "thread_draft.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(thread_posts, f, indent=4)
    return out_path
