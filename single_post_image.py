import requests
import json
import os
import uuid
import time
from dotenv import load_dotenv

load_dotenv()

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"

# Get proxy configuration
PROXY = os.getenv('PROXY')
PROXIES = {'http': PROXY, 'https': PROXY} if PROXY else None

# ======================================
# 🔥 FILL THESE FROM BROWSER SESSION
# ======================================
DOC_ID = "26168653472729001"

HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "x-fb-friendly-name": "CometPhotoRootContentQuery"}


# ======================================
# BUILD PAYLOAD
# ======================================

def build_payload(node_id, post_id):
    variables = {
        "isMediaset": True,
        "renderLocation": "comet_media_viewer",
        "nodeID": node_id,
        "mediasetToken": f"pcb.{post_id}",
        "scale": 2,
        "feedLocation": "COMET_MEDIA_VIEWER",
        "feedbackSource": 65,
        "focusCommentID": None,
        "privacySelectorRenderLocation": "COMET_MEDIA_VIEWER",
        "useDefaultActor": False,
        "shouldShowComments": True
    }

    return {
        "av": "0",
        "__user": "0",
        "__a": "1",
         "doc_id": DOC_ID,
        "variables": json.dumps(variables)
    }


# ======================================
# RAW CLEANING FUNCTIONS (MERGED)
# ======================================

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
                    except:
                        pass
                    i = j + 1
                    break
        else:
            break

    return blocks


def clean_data_blocks(blocks):
    cleaned = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block.pop("errors", None)
        block.pop("extensions", None)
        cleaned.append(block)
    return cleaned


def process_raw_graphql(raw_text):

    extracted = extract_data_blocks(raw_text)
    cleaned = clean_data_blocks(extracted)
    return cleaned


# ======================================
# DOWNLOAD IMAGE WITH RETRY
# ======================================

def download_image(url, folder, max_retries=3):
    """Download image with retry logic and proxy support"""
    os.makedirs(folder, exist_ok=True)
    
    filename = f"{uuid.uuid4()}.jpg"
    path = os.path.join(folder, filename)
    
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, proxies=PROXIES, timeout=30)
            r.raise_for_status()
            
            with open(path, "wb") as f:
                f.write(r.content)
            
            print(f"📥 Saved {filename}")
            return filename
        except Exception as e:
            print(f"  ⚠️ Download attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                wait_time = attempt * 2  # Exponential backoff: 2, 4, 6 seconds
                print(f"  ⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"  ❌ Failed to download after {max_retries} attempts")
                return None
    
    return None


# ======================================
# FETCH ALL IMAGES LOOP
# ======================================

def fetch_all_images(start_node_id, post_id):

    current_node = start_node_id
    visited = set()
    folder = f"album_{post_id}"

    while current_node and current_node not in visited:

        print(f"\n➡ Fetching node: {current_node}")
        visited.add(current_node)

        payload = build_payload(current_node, post_id)

        r = requests.post(GRAPHQL_URL, headers=HEADERS, data=payload, proxies=PROXIES)

        # Save RAW response
        os.makedirs("photo_raw", exist_ok=True)
        raw_path = f"photo_raw/{current_node}.txt"
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(r.text)

        print(f"💾 Raw saved → {raw_path}")

        # Clean using your parser
        cleaned_blocks = process_raw_graphql(r.text)

        if not cleaned_blocks:
            print("❌ No cleaned data found")
            break

        data = cleaned_blocks

        # ======================================
        # Extract current image
        # ======================================
        image_url = None
        for block in data:
            if "currMedia" in block:
                image_url = (
                    block["currMedia"]
                    .get("image", {})
                    .get("uri")
                )
                break

        if image_url:
            download_image(image_url, folder)
        else:
            print("❌ No image found")

        # ======================================
        # Extract next node
        # ======================================
        next_node = None
        for block in data:
            if "nextMediaAfterNodeId" in block and block["nextMediaAfterNodeId"]:
                node_id = block["nextMediaAfterNodeId"].get("id")
                if node_id:  # Only use if not null
                    next_node = node_id
                    break

        if next_node:
            print("➡ Next node:", next_node)
            current_node = next_node
        else:
            print("✅ No more images.")
            break


# ======================================
# RUN
# ======================================

if __name__ == "__main__":
    start_node = input("Enter first photo nodeID: ").strip()
    post_id = input("Enter post_id: ").strip()

    fetch_all_images(start_node, post_id)
