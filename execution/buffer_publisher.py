import os
import sys
import json
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs

def gql(query: str, variables: dict = None) -> dict:
    if not configs.BUFFER_ACCESS_TOKEN:
        raise ValueError("BUFFER_ACCESS_TOKEN is not set.")

    resp = requests.post(
        "https://api.buffer.com/graphql",
        json={"query": query, "variables": variables or {}},
        headers={
            "Authorization": f"Bearer {configs.BUFFER_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Buffer API HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Buffer GraphQL error: {data['errors']}")

    return data.get("data", {})

def publish_single_post(text: str):
    """
    Publishes a single post to Buffer Queue using GraphQL API.
    Does not use custom scheduling; simply adds to the automatic queue.
    """
    if not configs.BUFFER_PROFILE_ID:
        raise ValueError("BUFFER_PROFILE_ID is not set.")

    if not text:
        print("Empty post. Nothing to publish.")
        return

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post { id status }
        }
        ... on InvalidInputError { message }
        ... on UnauthorizedError { message }
      }
    }
    """

    variables = {
        "input": {
            "channelId": configs.BUFFER_PROFILE_ID,
            "text": text,
            "schedulingType": "automatic",
            "mode": "addToQueue"
        }
    }

    data = gql(mutation, variables)
    result = data.get("createPost", {})
    
    if "post" in result:
        print(f"Added to Queue. Post ID: {result['post']['id']}")
        return result['post']['id']
    
    if "message" in result:
        raise RuntimeError(f"Buffer Error: {result['message']}")
        
    return "unknown"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft", default=".tmp/final_posts.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    draft_path = configs.BASE_DIR / args.draft
    if draft_path.exists():
        with open(draft_path, "r", encoding="utf-8") as f:
            posts = json.load(f)
            
        if args.dry_run:
            print(f"DRY RUN. Would queue {len(posts)} posts:")
            for p in posts:
                print(f"- {p['content']}")
        else:
            for p in posts:
                publish_single_post(p["content"])
    else:
        print(f"File {draft_path} not found.")
