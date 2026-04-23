import json
import re

def score_virality(thread_posts: list) -> tuple:
    """
    Computes a deterministic virality score (0.0 to 1.0) for a thread.
    Returns (score, breakdown_dict)
    """
    if not thread_posts:
        return 0.0, {}

    # 1. Hook Score (0.25)
    # Check first post for questions, pattern interrupts, or high-signal words
    hook_post = thread_posts[0].get("content", "").lower()
    hook_score = 0.0
    if "?" in hook_post:
        hook_score += 0.5
    if any(w in hook_post for w in ["ternyata", "mitos", "alasan", "kenapa", "pernah", "rahasia", "fakta"]):
        hook_score += 0.5
    hook_score = min(1.0, hook_score)

    # 2. Readability Flow (0.20)
    # Avoid text walls. Good flow has mixed sentence lengths.
    readability_score = 1.0
    for post in thread_posts:
        content = post.get("content", "")
        # Penalize if it's just one massive run-on sentence
        if len(content) > 100 and "." not in content and "," not in content:
            readability_score -= 0.1
    readability_score = max(0.0, readability_score)

    # 3. Data Density (0.15)
    # Look for numbers, percentages, or [n] citations
    data_count = 0
    for post in thread_posts:
        content = post.get("content", "")
        if re.search(r'\d+%|\d+ |\[\d+\]', content):
            data_count += 1
    # Max score if at least 1/3 of posts have data
    data_target = max(1, len(thread_posts) // 3)
    data_score = min(1.0, data_count / data_target)

    # 4. Shareability (0.15)
    # Posts that are short and punchy (often quote-tweeted/reposted)
    shareable_count = sum(1 for p in thread_posts if 30 < len(p.get("content", "")) <= 100)
    shareability_score = min(1.0, shareable_count / 2) # Max score if at least 2 highly shareable posts

    # 5. Platform Fit (0.25)
    # Strict penalty if over 140 chars or orphan posts
    fit_score = 1.0
    for post in thread_posts:
        if len(post.get("content", "")) > 500:
            fit_score = 0.0 # Instant fail for platform constraint
            break
    
    # Check for CTA in the last post
    last_post = thread_posts[-1].get("content", "").lower()
    if not any(w in last_post for w in ["share", "gimana", "kalian", "komen", "👇", "?", "menurut"]):
        fit_score -= 0.2

    # Combine
    total_score = (
        (0.25 * hook_score) +
        (0.20 * readability_score) +
        (0.15 * data_score) +
        (0.15 * shareability_score) +
        (0.25 * fit_score)
    )

    breakdown = {
        "hook_score": hook_score,
        "readability_score": readability_score,
        "data_score": data_score,
        "shareability_score": shareability_score,
        "fit_score": fit_score,
        "total_score": round(total_score, 3)
    }

    return round(total_score, 3), breakdown

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            thread = json.load(f)
        score, bd = score_virality(thread)
        print(f"Total Score: {score}")
        print(json.dumps(bd, indent=2))
