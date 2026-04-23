import sys
import re
from pathlib import Path
import json

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs
from execution.buffer_publisher import publish_single_post
from execution.style_mutator import call_groq_api

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
        prompt = f"""You are a tech/AI thought leader on Threads. 
Write an engaging Threads post based on this insight:
{insight}

Make it sound natural, human, and straight to the point. No hashtags. No generic intro.
You have up to 500 characters. Provide a detailed, high-value post, but it MUST be strictly UNDER 500 characters.

Return ONLY a valid JSON object with a single key "post" containing your written post.
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
    insights_dir = configs.OBSIDIAN_RESEARCH_DIR / "AI_Insights"
    if not insights_dir.exists():
        print(f"Insights directory not found at {insights_dir}")
        return

    print(f"Scanning for pending AI Insights in {insights_dir}...")
    
    published_count = 0
    for md_file in insights_dir.glob("*.md"):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if it's pending
            if "status: pending" in content:
                print(f"Processing: {md_file.name}")
                
                # Extract or generate Threads content
                thread_content = extract_threads_post(content)
                if not thread_content:
                    print(f"  Failed to extract or generate thread content for {md_file.name}. Skipping.")
                    continue
                
                print(f"  Content ready. length: {len(thread_content)}")
                print(f"  Preview: {thread_content[:100]}...")
                
                # Publish to Buffer
                print("  Publishing to Buffer...")
                publish_single_post(thread_content)
                
                # Mark as published
                new_content = content.replace("status: pending", "status: published")
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                    
                print(f"  Marked {md_file.name} as published.")
                published_count += 1
                
        except Exception as e:
            print(f"Error processing {md_file.name}: {e}")

    print(f"\nDone. Published {published_count} new AI Insights to Threads.")

if __name__ == "__main__":
    process_ai_insights()
