import requests
import json
import time
import os
import uuid
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"

# ========= CONFIG (FILL THESE) =========
USER_ID = "100064551617529"   # profile / page id
DOC_ID = "25430544756617998" # ProfileCometTimelineFeedRefetchQuery

# ========= RETRY HELPER =========
def retry_request(url, headers, data, proxies, max_retries=5):
    """Make a POST request with retry logic"""
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, data=data, proxies=proxies, timeout=30)
            if r.status_code == 200:
                return r
            print(f"  ⚠️ Attempt {attempt}/{max_retries}: Status {r.status_code}")
        except Exception as e:
            print(f"  ⚠️ Attempt {attempt}/{max_retries}: {str(e)}")
        
        if attempt < max_retries:
            wait_time = attempt * 2  # Exponential backoff: 2, 4, 6, 8, 10 seconds
            print(f"  ⏳ Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    raise Exception(f"Failed after {max_retries} attempts")


def download_image(url, post_id, save_dir="page_post"):
    """Download image from URL and save with random UUID in post folder"""
    if not url or not post_id:
        return None
    
    try:
        # Create post-specific directory
        post_dir = os.path.join(save_dir, str(post_id))
        os.makedirs(post_dir, exist_ok=True)
        
        # Generate random UUID for filename
        random_id = str(uuid.uuid4())
        
        # Get file extension from URL or default to .jpg
        ext = ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".jpeg" in url.lower():
            ext = ".jpeg"
        
        filename = f"{random_id}{ext}"
        filepath = os.path.join(post_dir, filename)
        
        # Download the image
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Save the image
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"  📥 Downloaded image: {filename}")
        return filename
    
    except Exception as e:
        print(f"  ❌ Failed to download image: {str(e)}")
        return None

# -----------------------------
# Extract all "data" blocks from raw text
# -----------------------------
def extract_data_blocks(raw_text):
    blocks = []
    i = 0
    n = len(raw_text)

    while True:
        idx = raw_text.find('"data"', i)
        if idx == -1:
            break

        brace_start = raw_text.find('{', idx)
        if brace_start == -1:
            break

        depth = 0
        for j in range(brace_start, n):
            if raw_text[j] == '{':
                depth += 1
            elif raw_text[j] == '}':
                depth -= 1
                if depth == 0:
                    block_text = raw_text[brace_start:j+1]
                    try:
                        block = json.loads(block_text)
                        blocks.append(block)
                    except Exception:
                        pass
                    i = j + 1
                    break
        else:
            break

    return blocks


# -----------------------------
# Clean unwanted keys
# -----------------------------
def clean_data_blocks(blocks):
    cleaned = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        block.pop("errors", None)
        block.pop("extensions", None)

        cleaned.append(block)

    return cleaned


# -----------------------------
# Parse Facebook response using cleaning logic
# -----------------------------
def parse_fb_response(text):
    text = text.replace("for (;;);", "").strip()
    extracted = extract_data_blocks(text)
    cleaned = clean_data_blocks(extracted)
    
    # Return the cleaned array as-is
    return cleaned


BASE_HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "referer": f"https://www.facebook.com/profile.php?id={USER_ID}",
}

# Get proxy configuration
PROXY = os.getenv('PROXY')
PROXIES = {'http': PROXY, 'https': PROXY} if PROXY else None

if PROXY:
    print(f"Using proxy: {PROXY}")


def is_reel_or_video_post(node):
    """Check if the post is a reel or video post"""
    # Check for reel in story type
    story_type = node.get("__typename", "")
    if "reel" in story_type.lower():
        return True
    
    # Check if comet_sections has content that indicates reel
    comet_sections = node.get("comet_sections", {})
    content = comet_sections.get("content", {})
    
    # Check for reel in content typename
    content_typename = content.get("__typename", "")
    if "reel" in content_typename.lower():
        return True
    
    # Check attachments for video/reel content
    attachments = node.get("attachments") or []
    for att in attachments:
        styles = att.get("styles") or {}
        attachment = styles.get("attachment") or {}
        
        # Check if it's a video attachment
        single_media = attachment.get("media")
        if single_media:
            media_typename = single_media.get("__typename", "")
            if media_typename == "Video":
                return True
            # Check for reel in typename or anywhere in media object
            if "reel" in str(single_media).lower():
                return True
        
        # Check in all_subattachments for videos
        all_media = attachment.get("all_subattachments", {}).get("nodes", [])
        for m in all_media:
            media_node = m.get("media") or {}
            if media_node.get("__typename") == "Video":
                return True
            # Check for reel substring
            if "reel" in str(media_node).lower():
                return True
    
    return False


def extract_media(node, post_id):
    media = []

    attachments = node.get("attachments") or []
    for att in attachments:
        styles = att.get("styles") or {}
        attachment = styles.get("attachment") or {}

        # Check for single photo (direct media attachment)
        single_media = attachment.get("media")
        if single_media:
            # Single photo case
            if "photo_image" in single_media:
                image_url = single_media["photo_image"]["uri"]
                saved_filename = download_image(image_url, post_id)
                media.append({
                    "type": "photo",
                    "url": image_url,
                    "saved_as": saved_filename
                })
            elif "image" in single_media:
                image_url = single_media["image"]["uri"]
                saved_filename = download_image(image_url, post_id)
                media.append({
                    "type": "photo",
                    "url": image_url,
                    "saved_as": saved_filename
                })
            # Single video case
            if single_media.get("__typename") == "Video":
                media.append({
                    "type": "video",
                    "url": single_media.get("playable_url")
                })

        # Check for album (multiple photos/videos)
        all_media = attachment.get("all_subattachments", {}).get("nodes", [])
        for m in all_media:
            media_node = m.get("media") or {}

            if "image" in media_node:
                image_url = media_node["image"]["uri"]
                saved_filename = download_image(image_url, post_id)
                media.append({
                    "type": "photo",
                    "url": image_url,
                    "saved_as": saved_filename
                })

            if media_node.get("__typename") == "Video":
                media.append({
                    "type": "video",
                    "url": media_node.get("playable_url")
                })

    return media


def fetch_posts(limit):
    posts = []
    cursor = None
    page_num = 1  # Track page number for saving cleaned data

    while len(posts) < limit:
        variables = {
            "count": 3,
            "cursor": cursor,
            "id": USER_ID,
            "feedLocation": "TIMELINE",
            "renderLocation": "timeline",
            "scale": 2,
            "useDefaultActor": False
        }

        payload = {
        "av": "0",
        "__user": "0",
        "__a": "1",
            "doc_id": DOC_ID,
            "variables": json.dumps(variables),
        }

        r = retry_request(GRAPHQL_URL, BASE_HEADERS, payload, PROXIES)
        with open("response.txt", "w", encoding="utf-8") as f:
            f.write(r.text)
        print("Status code:", r.status_code)
        cleaned_data = parse_fb_response(r.text)
        
        # Save cleaned data for verification
        with open(f"cleaned_page_{page_num}.json", "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        print(f"Saved cleaned_page_{page_num}.json")
        
        # Collect all Story nodes from the response
        # Stories can be in two places:
        # 1. Inside timeline_list_feed_units.edges[]
        # 2. As standalone nodes with __typename: "Story"
        
        story_nodes = []
        timeline_block = None
        
        for block in cleaned_data:
            if not isinstance(block, dict):
                continue
            
            # Check if this block has timeline edges
            if "node" in block and "timeline_list_feed_units" in block.get("node", {}):
                timeline_block = block
                edges = block["node"]["timeline_list_feed_units"].get("edges", [])
                for edge in edges:
                    node = edge.get("node")
                    if node and node.get("__typename") == "Story":
                        story_nodes.append(node)
            
            # Check if this block itself is a Story node
            elif "node" in block and block["node"].get("__typename") == "Story":
                story_nodes.append(block["node"])
        
        print(f"Found {len(story_nodes)} posts in page {page_num}")
        
        # Process all collected Story nodes
        for node in story_nodes:
            # Skip reels and video posts
            if is_reel_or_video_post(node):
                print(f"  ⏭️  Skipping reel/video post")
                continue
            
            post_id = node.get("post_id")
            if not post_id:
                continue
                
            feedback_id = node.get("feedback", {}).get("id")

            message = (
                node.get("comet_sections", {})
                .get("content", {})
                .get("story", {})
                .get("message", {})
                .get("text")
            )

            permalink = None
            try:
                permalink = (
                    node["attachments"][0]["styles"]["attachment"]["url"]
                )
            except Exception:
                pass

            post = {
                "post_id": post_id,
                "feedback_id": feedback_id,
                "text": message,
                "permalink": permalink,
                "media": extract_media(node, post_id),
            }
            
            # Save individual post to its own folder
            post_dir = os.path.join("page_post", str(post_id))
            os.makedirs(post_dir, exist_ok=True)
            
            post_file = os.path.join(post_dir, "post.json")
            with open(post_file, "w", encoding="utf-8") as f:
                json.dump(post, f, ensure_ascii=False, indent=2)
            print(f"✓ Saved post {post_id} to {post_file}")

            posts.append(post)

            if len(posts) >= limit:
                break

        # update cursor - get page_info from timeline_block or find it in cleaned_data
        page_info = timeline_block["node"]["timeline_list_feed_units"].get("page_info")
        
        # If not in timeline_block, search for it in cleaned_data array
        if not page_info:
            for block in cleaned_data:
                if isinstance(block, dict) and "page_info" in block:
                    page_info = block["page_info"]
                    break
        
        page_info = page_info or {}
        cursor = page_info.get("end_cursor")

        if not cursor:
            print("No more pages. Stopping pagination.")
            break


        time.sleep(1)
        page_num += 1  # Increment page counter

    return posts


if __name__ == "__main__":
    count = int(input("How many posts to fetch? "))

    posts = fetch_posts(count)

    with open("posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(posts)} posts to posts.json")
