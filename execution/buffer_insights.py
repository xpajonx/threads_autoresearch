import sys
import json
import requests
from pathlib import Path

# Fix python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from execution.config import configs
from execution.buffer_publisher import gql

def fetch_buffer_posts():
    if not configs.BUFFER_ORG_ID:
        print("BUFFER_ORG_ID not set.")
        return

    # Query for posts in the organization
    query = """
    query GetPosts($orgId: OrganizationId!, $channelId: ChannelId!) {
      posts(input: { 
        organizationId: $orgId, 
        filter: { channelIds: [$channelId] } 
      }, first: 10) {
        edges {
          node {
            id
            text
            status
            sentAt
            dueAt
            channelService
          }
        }
      }
    }
    """
    
    try:
        variables = {
            "orgId": configs.BUFFER_ORG_ID,
            "channelId": configs.BUFFER_PROFILE_ID
        }
        data = gql(query, variables)
        posts_data = data.get("posts", {})
        edges = posts_data.get("edges", [])
        
        print(f"Fetched {len(edges)} posts from Buffer.")
        
        history = []
        for edge in edges:
            post = edge.get("node", {})
            history.append(post)
            print(f"\nPost ID: {post['id']}")
            print(f"Status: {post['status']}")
            print(f"Sent At: {post['sentAt']}")
            print(f"Text: {post['text'][:100]}...")
                
        out_path = configs.TMP_DIR / "buffer_posts_history.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
            
        return history
            
    except Exception as e:
        print(f"Failed to fetch Buffer posts: {e}")

if __name__ == "__main__":
    fetch_buffer_posts()
