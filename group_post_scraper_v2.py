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
GROUP_ID = "363757814515154"  # group id
DOC_ID = "25716860671307636"  # GroupsCometFeedRegularStoriesPaginationQuery

HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "referer": f"https://www.facebook.com/groups/{GROUP_ID}/",
}

# Get proxy configuration
PROXY = os.getenv('PROXY')
PROXIES = {'http': PROXY, 'https': PROXY} if PROXY else None

if PROXY:
    print(f"Using proxy: {PROXY}")

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


def download_image(url, post_id, image_index=1, save_dir="group_post"):
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


def extract_data_blocks(raw_text):
    """Extract all 'data' blocks from raw text"""
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


def clean_data_blocks(blocks):
    """Clean unwanted keys from data blocks"""
    cleaned = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        block.pop("errors", None)
        block.pop("extensions", None)

        cleaned.append(block)

    return cleaned


def parse_fb_response(text):
    """Parse Facebook response using the same logic as post_scraper"""
    text = text.replace("for (;;);", "").strip()
    extracted = extract_data_blocks(text)
    cleaned = clean_data_blocks(extracted)
    return cleaned


def is_reel_or_video_post(node):
    """Check if the post is a reel or video post"""
    if not node or node.get('__typename') != 'Story':
        return False
    
    # Check for reel in story type or anywhere in node
    node_typename = node.get('__typename', '')
    if 'reel' in node_typename.lower():
        return True
    
    # Check comet_sections for reel content
    comet_sections = node.get('comet_sections', {})
    content = comet_sections.get('content', {})
    
    content_typename = content.get('__typename', '')
    if 'reel' in content_typename.lower():
        return True
    
    # Check attachments for video/reel content
    attachments = node.get('attachments', [])
    for attachment in attachments:
        # Check for video media type
        if 'media' in attachment and attachment['media'].get('__typename') == 'Video':
            return True
        
        # Check for reel substring in media object
        if 'media' in attachment and 'reel' in str(attachment['media']).lower():
            return True
        
        # Check in styles > attachment > media for video or reel
        styles_media = attachment.get('styles', {}).get('attachment', {}).get('media', {})
        if styles_media.get('__typename') == 'Video':
            return True
        if 'reel' in str(styles_media).lower():
            return True
        
        # Check all_subattachments for videos or reels
        for subattachment in attachment.get('all_subattachments', {}).get('nodes', []):
            if 'media' in subattachment and subattachment['media'].get('__typename') == 'Video':
                return True
            if 'media' in subattachment and 'reel' in str(subattachment['media']).lower():
                return True
    
    return False


def extract_media(node, post_id):
    """Extract photo and video URLs from a post"""
    media = {
        'photos': [],
        'videos': []
    }
    
    # Track image index for this post
    image_index = 0
    
    attachments = node.get('attachments', [])
    
    for attachment in attachments:
        # Handle photo attachments
        if 'media' in attachment and attachment['media'].get('__typename') == 'Photo':
            # Try to get photo from styles > attachment > media structure
            photo_data = attachment.get('styles', {}).get('attachment', {}).get('media', {})
            if 'photo_image' in photo_data:
                image_index += 1
                image_url = photo_data['photo_image'].get('uri')
                saved_filename = download_image(image_url, post_id, image_index)
                media['photos'].append({
                    'id': attachment['media'].get('id'),
                    'url': image_url,
                    'width': photo_data['photo_image'].get('width'),
                    'height': photo_data['photo_image'].get('height'),
                    'saved_as': saved_filename
                })
        
        # Handle albums (multiple photos)
        if 'all_subattachments' in attachment:
            for subattachment in attachment.get('all_subattachments', {}).get('nodes', []):
                if 'media' in subattachment and subattachment['media'].get('__typename') == 'Photo':
                    image_index += 1
                    photo_data = subattachment.get('media', {})
                    if 'image' in photo_data:
                        image_url = photo_data['image'].get('uri')
                        saved_filename = download_image(image_url, post_id, image_index)
                        media['photos'].append({
                            'id': photo_data.get('id'),
                            'url': image_url,
                            'width': photo_data['image'].get('width'),
                            'height': photo_data['image'].get('height'),
                            'saved_as': saved_filename
                        })
        
        # Handle video attachments
        if 'media' in attachment and attachment['media'].get('__typename') == 'Video':
            video_data = attachment.get('media', {})
            media['videos'].append({
                'id': video_data.get('id'),
                'url': video_data.get('playable_url'),
                'thumbnail': video_data.get('preferred_thumbnail', {}).get('image', {}).get('uri')
            })
    
    return media


def extract_post_data(node):
    """Extract relevant data from a post node"""
    if not node or node.get('__typename') != 'Story':
        return None
    
    # Get the post content from the nested structure
    content_story = node.get('comet_sections', {}).get('content', {}).get('story', {})
    
    # Extract message/text
    message = ''
    message_obj = content_story.get('message', {})
    if message_obj:
        message = message_obj.get('text', '')
    
    post_id = node.get('post_id')
    if not post_id:
        return None
    
    post_data = {
        'id': node.get('id'),
        'post_id': post_id,
        'message': message,
        'permalink': node.get('permalink_url', ''),
        'photos': extract_media(node, post_id)['photos'],
        'videos': extract_media(node, post_id)['videos']
    }
    
    # Save individual post to its own folder as {post_id}.json
    post_dir = os.path.join("group_post", str(post_id))
    os.makedirs(post_dir, exist_ok=True)
    
    post_file = os.path.join(post_dir, f"{post_id}.json")
    with open(post_file, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
    print(f"✓ Saved to {post_file}")
    
    return post_data


def fetch_posts(limit=10):
    """Fetch posts from Facebook group"""
    posts = []
    cursor = None
    page_num = 1
    
    while len(posts) < limit:
        print(f"\nFetching page {page_num}...")
        
        variables = {
            "count": 3,
            "cursor": cursor,
            "feedLocation": "GROUP",
            "feedType": "DISCUSSION",
            "feedbackSource": 0,
            "filterTopicId": None,
            "focusCommentID": None,
            "privacySelectorRenderLocation": "COMET_STREAM",
            "renderLocation": "group",
            "scale": 2,
            #"sortingSetting": "TOP_POSTS",
            "stream_initial_count": 1,
            "useDefaultActor": False,
            "id": GROUP_ID,
        }
        
        payload = {
            "av": "0",
            "__user": "0",
            "__a": "1",
            "doc_id": DOC_ID,
            "variables": json.dumps(variables),
        }
        
        try:
            r = retry_request(GRAPHQL_URL, HEADERS, payload, PROXIES)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            break
        
        # Parse the response
        data = parse_fb_response(r.text)
        
        if not data:
            print("No data received")
            break
        
        # Save raw response for debugging
        # with open(f"group_raw_page_{page_num}.json", "w", encoding="utf-8") as f:
        #     json.dump(data, f, ensure_ascii=False, indent=2)
        # print(f"Saved group_raw_page_{page_num}.json")
        
        # Extract posts from the response array
        posts_found = 0
        next_cursor = None
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            # Check if this item has a 'node' with a Story
            if 'node' in item and item['node'].get('__typename') == 'Story':
                # Skip reels and video posts
                if is_reel_or_video_post(item['node']):
                    print(f"  ⏭️  Skipping reel/video post")
                    continue
                
                post_data = extract_post_data(item['node'])
                if post_data:
                    posts.append(post_data)
                    posts_found += 1
                    print(f"  - Found post: {post_data['post_id']}")
                    
                    if len(posts) >= limit:
                        break
            
            # Look for pagination info
            elif 'page_info' in item:
                page_info = item['page_info']
                if page_info.get('has_next_page'):
                    next_cursor = page_info.get('end_cursor')
        
        print(f"Found {posts_found} posts on this page")
        
        # Check if we should continue
        if not next_cursor or len(posts) >= limit:
            print("No more pages or reached limit. Stopping.")
            break
        
        cursor = next_cursor
        page_num += 1
        time.sleep(2)  # Be nice to the server
    
    return posts


if __name__ == "__main__":
    count = int(input("How many posts to fetch? "))
    
    print(f"\nFetching {count} posts from group {GROUP_ID}...")
    posts = fetch_posts(count)
    
    # Save posts to file
    with open("group_posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved {len(posts)} posts to group_posts.json")
    
    # Print summary
    print("\nSummary:")
    for i, post in enumerate(posts, 1):
        photos = len(post['photos'])
        videos = len(post['videos'])
        print(f"{i}. Post ID: {post['post_id']}")
        if photos:
            print(f"   📷 {photos} photo(s)")
        if videos:
            print(f"   🎥 {videos} video(s)")
        if post['message']:
            preview = post['message'][:100] + '...' if len(post['message']) > 100 else post['message']
            print(f"   {preview}")
