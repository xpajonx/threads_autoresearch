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
    Parses Source_of_Truth.md into discrete data points.
    1. Tries to find 'Klaim' and 'Bukti' pairs.
    2. Fallback: Uses Level 3 Headers (###) as claims and following text as evidence.
    """
    sot_path = topic_dir / "Source_of_Truth.md"
    if not sot_path.exists():
        raise FileNotFoundError(f"Missing {sot_path}")
        
    with open(sot_path, "r", encoding="utf-8") as f:
        content = f.read()

    data_points = []
    
    # Strategy 1: Klaim/Bukti pairs
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

    # Strategy 2: Fallback to Headers (###)
    if not data_points:
        print(f"DEBUG: No Klaim/Bukti found in {sot_path.name}. Trying header-based fallback...")
        # Find all ### Headers
        sections = re.split(r"(?=\n### )", "\n" + content)
        for section in sections:
            section = section.strip()
            if not section.startswith("###"): continue
            
            lines = section.splitlines()
            # Header is the claim
            claim = lines[0].replace("###", "").strip()
            # Everything else is evidence
            evidence = " ".join([l.strip() for l in lines[1:] if l.strip()])
            
            if claim and evidence:
                # Remove common list prefixes like "1. ", "2. "
                claim = re.sub(r"^\d+\.\s*", "", claim)
                data_points.append({"claim": claim, "evidence": evidence[:500]})

    if not data_points:
        print(f"DEBUG: Still could not parse {sot_path.name}. First 5 lines:")
        for i, line in enumerate(content.splitlines()[:5]):
            print(f"  L{i+1}: {repr(line)}")
            
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
