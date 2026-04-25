import sys
import re
from pathlib import Path
import json

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs
from execution.buffer_publisher import publish_single_post
from execution.style_mutator import call_groq_api

def load_voice_profile() -> dict:
    """Load voice_profile.json."""
    voice_path = Path(__file__).resolve().parent / "voice_profile.json"
    if voice_path.exists():
        with open(voice_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def extract_threads_post(content: str) -> str:
    """Extract the Draft Threads Post section from the markdown content."""
    # Look for the section under ## Draft Threads Post
    match = re.search(r"## Draft Threads Post\n(.*?)(?:\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # If not found, try to extract The Insight / Tip
    match = re.search(r"## The Insight / Tip\n(.*?)(?:\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
    if match:
        insight = match.group(1).strip()
        # Fallback: Let Groq write a thread post based on the insight
        voice = load_voice_profile()
        pronouns = voice.get('pronouns', ['gue', 'lo'])
        exemplars = voice.get('exemplar_hooks', [])
        exemplar_str = exemplars[0] if exemplars else ""
        forbidden = voice.get('forbidden_words', [])
        
        prompt = f"""You are a tech/AI thought leader on Threads for {voice.get('threads_handle', '@m.fauzan.aziz')}. 
Write an engaging Threads post based on this insight:
{insight}

LANGUAGE RULE (WAJIB / MANDATORY):
- Tulis SELURUHNYA dalam Bahasa Indonesia percakapan (conversational Indonesian).
- Gunakan pronoun "{pronouns[0]}" dan "{pronouns[1]}" secara natural.
- Boleh pakai istilah English untuk tech terms (contoh: AI, machine learning, automation).
- JANGAN tulis dalam bahasa Inggris. Jika output dalam English, itu GAGAL.

CONTOH GAYA PENULISAN:
"{exemplar_str}"

VOICE CONSTRAINTS:
- Persona: {voice.get('persona', 'The Relatable Intellectual')}
- Style: {', '.join(voice.get('style_markers', []))}
- Forbidden words: {', '.join(forbidden)}

STRICT PLATFORM RULES:
1. The post MUST be in Indonesian (Bahasa Indonesia). English output = FAILED.
2. Make it sound natural, human, and straight to the point. No hashtags. No generic intro.
3. You have up to 500 characters. Provide a detailed, high-value post, but it MUST be strictly UNDER 500 characters.
4. Do not use AI-isms (like 'essentially', 'in conclusion', 'landscape', 'delve into').

Return ONLY a valid JSON object with a single key "post" containing your written post in Indonesian.
"""
        try:
            response_text = call_groq_api(prompt)
            result_json = json.loads(response_text)
            return result_json.get("post", "").strip()
        except Exception as e:
            print(f"Failed to generate thread from Groq: {e}")
            return ""
    
    return ""

def process_ai_insights():
    # Try multiple common locations for AI_Insights
    possible_paths = [
        configs.OBSIDIAN_RESEARCH_DIR / "AI_Insights",
        configs.OBSIDIAN_RESEARCH_DIR.parent / "AI_Insights",
    ]
    
    insights_dir = None
    for path in possible_paths:
        if path.exists() and path.is_dir():
            insights_dir = path
            break

    if not insights_dir:
        print(f"DEBUG: AI_Insights directory not found in: {[str(p) for p in possible_paths]}")
        return

    print(f"Scanning for pending AI Insights in {insights_dir}...")
    
    files = list(insights_dir.glob("*.md"))
    print(f"Found {len(files)} markdown files total.")

    published_count = 0
    for md_file in files:
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Case-insensitive status check
            status_match = re.search(r"status:\s*pending", content, re.IGNORECASE)
            if status_match:
                print(f"Processing: {md_file.name}")
                
                # Extract or generate Threads content
                thread_content = extract_threads_post(content)
                if not thread_content:
                    print(f"  [ERROR] Failed to extract or generate thread content for {md_file.name}. Skipping.")
                    continue
                
                print(f"  Content ready. length: {len(thread_content)}")
                
                # Publish to Buffer
                print("  Publishing to Buffer...")
                publish_single_post(thread_content)
                
                # Mark as published (preserving original case for the label if possible, but standardizing value)
                new_content = re.sub(r"status:\s*pending", "status: published", content, flags=re.IGNORECASE)
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                    
                print(f"  Marked {md_file.name} as published.")
                published_count += 1
            else:
                # Debug: why was it skipped?
                if "status:" in content.lower():
                    current_status = re.search(r"status:\s*(\w+)", content, re.IGNORECASE)
                    print(f"  Skipping {md_file.name}: status is '{current_status.group(1) if current_status else 'unknown'}'")
                
        except Exception as e:
            print(f"Error processing {md_file.name}: {e}")

    print(f"\nDone. Published {published_count} new AI Insights to Threads.")

if __name__ == "__main__":
    process_ai_insights()
