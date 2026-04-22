import os
import sys
import json
from pathlib import Path

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

def extract_voice_profile():
    print("Starting voice profile extraction...")
    
    # Base persona elements
    profile = {
        "persona": "The Relatable Intellectual",
        "pronouns": ["gue", "lo"],
        "forbidden_words": ["essentially", "in conclusion", "landscape", "delve into", "tapestry"],
        "style_markers": [
            "Opens with personal anecdote or local cultural observation",
            "Pivots to data-backed insight after relatable setup",
            "Uses questions to create information gaps",
            "Conversational Indonesian with occasional English terms",
            "Critical/analytical tone, not preachy"
        ],
        "exemplar_hooks": [],
        "x_handle": "@xpajonx",
        "threads_handle": "@m.fauzan.aziz"
    }

    # Extract hooks from the essay
    essay_path = configs.OBSIDIAN_RESEARCH_DIR / "Kenapa_Manusia_Takut_Sendiri" / "Essay_Kesendirian_Threads.md"
    if essay_path.exists():
        print(f"Reading essay from {essay_path}")
        with open(essay_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Extremely naive hook extraction for the first paragraph after title
            paragraphs = content.split('\n\n')
            for p in paragraphs:
                if "gue ngebaca" in p or "kepikiran" in p:
                    profile["exemplar_hooks"].append(p.strip()[:140] + "...")
                    break
    
    # Optionally enrich with Tavily if available
    if TavilyClient and configs.TAVILY_API_KEY and configs.TAVILY_API_KEY != 'tvly-placeholder':
        try:
            print("Enriching from X/Twitter via Tavily...")
            client = TavilyClient(api_key=configs.TAVILY_API_KEY)
            res = client.search(f'site:x.com "{profile["x_handle"]}"', search_depth="basic")
            for result in res.get("results", [])[:2]:
                snippet = result.get("content", "")
                if snippet:
                    # We might add it to exemplars if it's not a generic UI text
                    pass 
        except Exception as e:
            print(f"Tavily enrichment failed: {e}")
            
    # Fallback exemplars if empty
    if not profile["exemplar_hooks"]:
        profile["exemplar_hooks"] = [
            "Beberapa waktu lalu gue ngebaca post X yang isinya cukup menggelitik...",
            "Pertanyaan tadi menggelitik karena gue jadi kepikiran..."
        ]

    out_path = configs.EXECUTION_DIR / "voice_profile.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=4)
        
    print(f"Voice profile successfully written to {out_path}")

if __name__ == "__main__":
    extract_voice_profile()
