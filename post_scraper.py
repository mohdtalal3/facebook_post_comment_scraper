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
USER_ID = "100019577483175"   # profile / page id
PAGE_NAME = None  # Will be extracted automatically
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


def download_image(url, post_id, image_index=1, save_dir="page_post"):
    """Download image from URL and save as {post_id}.jpg or {post_id}_2.jpg etc"""
    if not url or not post_id:
        return None
    
    try:
        # Create post-specific directory
        post_dir = os.path.join(save_dir, str(post_id))
        os.makedirs(post_dir, exist_ok=True)
        
        # Get file extension from URL or default to .jpg
        ext = ".jpg"
        if ".png" in url.lower():
            ext = ".png"
        elif ".jpeg" in url.lower():
            ext = ".jpeg"
        
        # Name as {post_id}.jpg or {post_id}_2.jpg etc
        filename = f"{post_id}{ext}" if image_index == 1 else f"{post_id}_{image_index}{ext}"
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


def fetch_remaining_images(last_media_id, post_id, current_image_count, save_dir="page_post"):
    """Fetch remaining images using media ID iteration (for posts with 5+ images)"""
    if not last_media_id or not post_id:
        return []
    
    print(f"  🔄 Fetching remaining images after image #{current_image_count}...")
    
    DOC_ID_PHOTO = "26168653472729001"  # CometPhotoRootContentQuery
    HEADERS_PHOTO = {
        "user-agent": "Mozilla/5.0",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.facebook.com",
        "x-fb-friendly-name": "CometPhotoRootContentQuery"
    }
    
    remaining_photos = []
    current_node = last_media_id
    visited = set()
    image_index = current_image_count + 1
    
    while current_node and current_node not in visited and image_index <= 50:  # Max 50 images safety limit
        visited.add(current_node)
        
        variables = {
            "isMediaset": True,
            "renderLocation": "comet_media_viewer",
            "nodeID": current_node,
            "mediasetToken": f"pcb.{post_id}",
            "scale": 2,
            "feedLocation": "COMET_MEDIA_VIEWER",
            "feedbackSource": 65,
            "focusCommentID": None,
            "privacySelectorRenderLocation": "COMET_MEDIA_VIEWER",
            "useDefaultActor": False,
            "shouldShowComments": True
        }
        
        payload = {
            "av": "0",
            "__user": "0",
            "__a": "1",
            "doc_id": DOC_ID_PHOTO,
            "variables": json.dumps(variables)
        }
        
        try:
            r = requests.post(GRAPHQL_URL, headers=HEADERS_PHOTO, data=payload, proxies=PROXIES, timeout=30)
            if r.status_code != 200:
                break
            
            # Parse response
            cleaned_blocks = parse_fb_response(r.text)
            if not cleaned_blocks:
                break
            
            # Extract current image URL
            image_url = None
            for block in cleaned_blocks:
                if "currMedia" in block:
                    image_url = block["currMedia"].get("image", {}).get("uri")
                    break
            
            if image_url:
                saved_filename = download_image(image_url, post_id, image_index, save_dir)
                if saved_filename:
                    remaining_photos.append({
                        'type': 'photo',
                        'url': image_url,
                        'saved_as': saved_filename
                    })
                    image_index += 1
            
            # Extract next node
            next_node = None
            for block in cleaned_blocks:
                if "nextMediaAfterNodeId" in block and block["nextMediaAfterNodeId"]:
                    node_id = block["nextMediaAfterNodeId"].get("id")
                    if node_id:
                        next_node = node_id
                        break
            
            if next_node:
                current_node = next_node
                time.sleep(0.5)  # Small delay between requests
            else:
                break  # No more images
                
        except Exception as e:
            print(f"  ⚠️ Error fetching next image: {e}")
            break
    
    if remaining_photos:
        print(f"  ✅ Fetched {len(remaining_photos)} additional images")
    
    return remaining_photos


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


def extract_page_name(node):
    """Extract page/user name from post node"""
    try:
        # Try from actors
        actors = node.get('comet_sections', {}).get('content', {}).get('story', {}).get('actors', [])
        if actors and len(actors) > 0:
            return actors[0].get('name')
        
        # Try from feedback > owning_profile
        feedback = node.get('feedback', {})
        owning_profile = feedback.get('owning_profile', {})
        if owning_profile:
            return owning_profile.get('name') or owning_profile.get('short_name')
        
        return None
    except Exception:
        return None


def extract_comment_count(node):
    """Extract comment count from post node"""
    try:
        # Path 1: feedback.comment_rendering_instance.comments.total_count
        comment_count = node.get("feedback", {}).get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 2: comet_sections.feedback.story.story_ufi_container.story.feedback_context.feedback_target_with_context.comment_rendering_instance.comments.total_count
        comet_sections = node.get("comet_sections", {})
        feedback_section = comet_sections.get("feedback", {})
        story = feedback_section.get("story", {})
        story_ufi_container = story.get("story_ufi_container", {})
        ufi_story = story_ufi_container.get("story", {})
        feedback_context = ufi_story.get("feedback_context", {})
        feedback_target = feedback_context.get("feedback_target_with_context", {})
        comment_count = feedback_target.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 3: comet_sections.feedback.story.story_ufi_container.story.feedback_context.feedback_target_with_context.comet_ufi_summary_and_actions_renderer.feedback.comment_rendering_instance.comments.total_count
        comet_ufi = feedback_target.get("comet_ufi_summary_and_actions_renderer", {}).get("feedback", {})
        comment_count = comet_ufi.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 4: comet_sections.feedback.story.feedback_context.feedback_target_with_context.comment_rendering_instance.comments.total_count (old structure)
        comet_sections = node.get("comet_sections", {})
        feedback_section = comet_sections.get("feedback", {})
        story = feedback_section.get("story", {})
        feedback_context = story.get("feedback_context", {})
        feedback_target = feedback_context.get("feedback_target_with_context", {})
        comment_count = feedback_target.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
        
        # Path 5: feedback.comments_count_summary_renderer.feedback.comment_rendering_instance.comments.total_count
        comments_renderer = node.get("feedback", {}).get("comments_count_summary_renderer", {}).get("feedback", {})
        comment_count = comments_renderer.get("comment_rendering_instance", {}).get("comments", {}).get("total_count")
        if comment_count is not None:
            return comment_count
            
        return 0
    except Exception:
        return 0


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


# Global counter for tracking image indices per post
_image_counters = {}

def extract_media(node, post_id, save_dir="page_post"):
    global _image_counters
    
    # Initialize counter for this post if not exists
    if post_id not in _image_counters:
        _image_counters[post_id] = 0
    
    media = []
    last_media_id = None

    attachments = node.get("attachments") or []
    for att in attachments:
        styles = att.get("styles") or {}
        attachment = styles.get("attachment") or {}

        # Check for single photo (direct media attachment)
        single_media = attachment.get("media")
        if single_media:
            # Single photo case
            if "photo_image" in single_media:
                _image_counters[post_id] += 1
                last_media_id = single_media.get("id")  # Track the last media ID
                image_url = single_media["photo_image"]["uri"]
                saved_filename = download_image(image_url, post_id, _image_counters[post_id], save_dir)
                media.append({
                    "type": "photo",
                    "url": image_url,
                    "saved_as": saved_filename
                })
            elif "image" in single_media:
                _image_counters[post_id] += 1
                last_media_id = single_media.get("id")  # Track the last media ID
                image_url = single_media["image"]["uri"]
                saved_filename = download_image(image_url, post_id, _image_counters[post_id], save_dir)
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
                _image_counters[post_id] += 1
                last_media_id = media_node.get("id")  # Track the last media ID
                image_url = media_node["image"]["uri"]
                saved_filename = download_image(image_url, post_id, _image_counters[post_id], save_dir)
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
    
    # Fetch remaining images if we have exactly 5 photos (indicating there may be more)
    photo_count = sum(1 for m in media if m.get("type") == "photo")
    if photo_count == 5 and last_media_id:
        remaining_photos = fetch_remaining_images(last_media_id, post_id, _image_counters[post_id], save_dir)
        media.extend(remaining_photos)

    return media


def post_already_exists(post_id, base_folder, name_folder):
    """Check if a post has already been scraped by checking if its JSON file exists"""
    if not post_id or not name_folder:
        return False
    
    post_file = os.path.join(base_folder, name_folder, str(post_id), f"{post_id}.json")
    return os.path.exists(post_file)


def fetch_posts(limit=10, min_comments=0, batch_size=10, on_batch_complete=None):
    """Fetch posts from Facebook page
    
    Args:
        limit: Maximum number of posts to fetch
        min_comments: Minimum number of comments required for a post to be included (0 = no filter)
        batch_size: Number of posts to fetch before calling on_batch_complete callback
        on_batch_complete: Optional callback function(batch_posts, total_so_far, limit) called after each batch
    """
    global PAGE_NAME
    all_posts = []
    batch_posts = []
    cursor = None
    page_num = 1  # Track page number for saving cleaned data
    
    if min_comments > 0:
        print(f"📊 Filtering posts with at least {min_comments} comments")
    
    if batch_size > 0 and batch_size < limit:
        print(f"📦 Processing in batches of {batch_size} posts")

    while len(all_posts) < limit:
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

        # Retry loop for empty response handling
        max_empty_retries = 3
        empty_retry_count = 0
        cleaned_data = []
        
        while empty_retry_count < max_empty_retries:
            r = retry_request(GRAPHQL_URL, BASE_HEADERS, payload, PROXIES)
            # with open("response.txt", "w", encoding="utf-8") as f:
            #     f.write(r.text)
            print("Status code:", r.status_code)
            cleaned_data = parse_fb_response(r.text)
            
            if cleaned_data and len(cleaned_data) > 0:
                # Got valid data, break retry loop
                break
            else:
                empty_retry_count += 1
                if empty_retry_count < max_empty_retries:
                    print(f"  ⚠️ Empty response, retrying ({empty_retry_count}/{max_empty_retries})...")
                    time.sleep(2)  # Wait before retry
                else:
                    print(f"  ❌ Empty response after {max_empty_retries} attempts, skipping page")
        
        # Save cleaned data for verification
        with open(f"cleaned_page_{page_num}.json", "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        print(f"Saved cleaned_page_{page_num}.json")
        
        # If still empty after retries, stop pagination (can't get next cursor from empty response)
        if not cleaned_data or len(cleaned_data) == 0:
            print("  ❌ No data received after retries, stopping pagination")
            break
        
        # Collect all Story nodes from the response
        # Stories can be in two places:
        # 1. Inside timeline_list_feed_units.edges[]
        # 2. As standalone nodes with __typename: "Story"
        
        story_nodes = []
        timeline_block = None
        
        for block in cleaned_data:
            if not isinstance(block, dict):
                continue
            
            node = block.get("node", {})
            node_typename = node.get("__typename")
            
            # Check if this block has timeline edges
            if "timeline_list_feed_units" in node:
                timeline_block = block
                edges = node["timeline_list_feed_units"].get("edges", [])
                for edge in edges:
                    edge_node = edge.get("node")
                    if edge_node and edge_node.get("__typename") == "Story":
                        story_nodes.append(edge_node)
            
            # Check if this block itself is a Story node
            elif node_typename == "Story":
                story_nodes.append(node)
            
            # Check for Story nodes inside Group edges (edge case)
            elif node_typename == "Group":
                edges = node.get('group_feed', {}).get('edges', [])
                for edge in edges:
                    edge_node = edge.get('node', {})
                    if edge_node.get('__typename') == 'Story':
                        story_nodes.append(edge_node)
        
        print(f"Found {len(story_nodes)} posts in page {page_num}")
        
        # Process all collected Story nodes
        for node in story_nodes:
            # Skip reels and video posts
            if is_reel_or_video_post(node):
                print(f"  ⏭️  Skipping reel/video post")
                continue
            
            # Check comment count threshold
            comment_count = extract_comment_count(node)
            if min_comments > 0 and comment_count < min_comments:
                print(f"  ⏭️  Skipping post with only {comment_count} comments (need {min_comments}+)")
                continue
            
            # Extract page name from first post if not set
            if not PAGE_NAME:
                PAGE_NAME = extract_page_name(node)
                if PAGE_NAME:
                    print(f"📂 Page name: {PAGE_NAME}")
            
            post_id = node.get("post_id")
            if not post_id:
                continue
            
            # Check if post already exists
            temp_page_name = PAGE_NAME or extract_page_name(node)
            if temp_page_name:
                temp_name_folder = "".join(c for c in temp_page_name if c.isalnum() or c in (' ', '-', '_')).strip() or "Unknown"
                if post_already_exists(post_id, "page_post", temp_name_folder):
                    print(f"  ⏭️  Skipping already scraped post: {post_id}")
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
                "comment_count": comment_count,
                "page_name": PAGE_NAME,
            }
            
            # Sanitize page name folder
            if PAGE_NAME:
                name_folder = "".join(c for c in PAGE_NAME if c.isalnum() or c in (' ', '-', '_')).strip()
                if not name_folder:
                    name_folder = "Unknown"
            else:
                name_folder = "Unknown"
            
            # Prepare save directory for media
            media_save_dir = os.path.join("page_post", name_folder)
            
            # Extract media with correct save directory
            post["media"] = extract_media(node, post_id, media_save_dir)
            
            # Save individual post to folder structure: page_post/{page_name}/{post_id}/{post_id}.json
            post_dir = os.path.join("page_post", name_folder, str(post_id))
            os.makedirs(post_dir, exist_ok=True)
            
            post_file = os.path.join(post_dir, f"{post_id}.json")
            with open(post_file, "w", encoding="utf-8") as f:
                json.dump(post, f, ensure_ascii=False, indent=2)
            print(f"✓ Saved to {post_file}")

            batch_posts.append(post)
            all_posts.append(post)
            
            # Check if we should process this batch
            if batch_size > 0 and len(batch_posts) >= batch_size and on_batch_complete:
                print(f"\n📦 Batch complete: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
                on_batch_complete(batch_posts, len(all_posts), limit)
                batch_posts = []  # Reset batch
            
            if len(all_posts) >= limit:
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
    
    # Process any remaining posts in the final batch
    if batch_posts and on_batch_complete:
        print(f"\n📦 Final batch: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
        on_batch_complete(batch_posts, len(all_posts), limit)

    return all_posts


if __name__ == "__main__":
    count = int(input("How many posts to fetch? "))

    posts = fetch_posts(count)

    with open("posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    print(f"Saved {len(posts)} posts to posts.json")
