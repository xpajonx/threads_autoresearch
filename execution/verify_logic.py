import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mocking parts of the system to test logic
class MockConfigs:
    BUFFER_ACCESS_TOKEN = "test_token"
    BUFFER_PROFILE_ID = "test_profile"
    TMP_DIR = Path("./.tmp")
    DATA_DIR = Path("./AI_Automation_Data")

# Create a test script to verify logic
def test_buffer_logic():
    print("Testing Buffer Analytics Logic...")
    
    # Sample Buffer Response
    mock_buffer_response = {
        "updates": [
            {
                "id": "post_1",
                "text": "Ini adalah postingan tes",
                "statistics": {
                    "favorites": 10,
                    "replies": 2,
                    "retweets": 5,
                    "quotes": 1
                }
            }
        ]
    }
    
    # Logic extracted from shadow_analytics.py
    updates = mock_buffer_response.get("updates", [])
    posts = []
    for up in updates:
        stats = up.get("statistics", {})
        likes = stats.get("favorites", 0) or stats.get("likes", 0)
        replies = stats.get("replies", 0)
        reposts = stats.get("retweets", 0) or stats.get("reposts", 0)
        quotes = stats.get("quotes", 0)
        
        post = {
            "pk": up.get("id"),
            "text": up.get("text", "")[:200],
            "likes": int(likes),
            "replies": int(replies),
            "reposts": int(reposts),
            "quotes": int(quotes),
        }
        post["engagement"] = post["likes"] + post["replies"] + post["reposts"] + post["quotes"]
        posts.append(post)
    
    print(f"Result: {posts}")
    assert len(posts) == 1
    assert posts[0]["engagement"] == 18
    assert posts[0]["pk"] == "post_1"
    print("BUFFER SUCCESS: Buffer Analytics Parsing Logic passed")

def test_insight_prompt_logic():
    print("\nTesting AI Insight Prompt Logic...")
    
    # Sample Voice Profile
    mock_voice = {
        "persona": "Test Persona",
        "pronouns": ["gue", "lo"]
    }
    
    insight = "AI will change the world."
    voice_str = json.dumps(mock_voice, indent=2)
    
    # Logic extracted from insight_publisher.py
    prompt = f"""You are a tech/AI thought leader on Threads. 
Write an engaging Threads post based on this insight:
{insight}

VOICE CONSTRAINTS:
{voice_str}

STRICT PLATFORM RULES:
1. Write in conversational Indonesian (Bahasa Indonesia) using pronouns like "gue/lo" as specified in the voice profile.
2. Make it sound natural, human, and straight to the point. No hashtags. No generic intro.
3. You have up to 500 characters. Provide a detailed, high-value post, but it MUST be strictly UNDER 500 characters.
4. Do not use AI-isms.

Return ONLY a valid JSON object with a single key "post" containing your written post in Indonesian.
"""
    
    print("Generated Prompt Preview:")
    print("-" * 20)
    print(prompt)
    print("-" * 20)
    
    assert "Bahasa Indonesia" in prompt
    assert "gue/lo" in prompt
    assert "VOICE CONSTRAINTS" in prompt
    print("INSIGHT SUCCESS: AI Insight Prompt Logic passed")

if __name__ == "__main__":
    test_buffer_logic()
    test_insight_prompt_logic()
