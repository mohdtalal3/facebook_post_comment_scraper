import requests
import json
import time

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"

# ========= CONFIG (FILL THESE) =========
USER_ID = "100057388541815"   # profile / page id
DOC_ID = "25430544756617998" # ProfileCometTimelineFeedRefetchQuery

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


HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "referer": f"https://www.facebook.com/profile.php?id={USER_ID}",
}


def extract_media(node):
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
                media.append({
                    "type": "photo",
                    "url": single_media["photo_image"]["uri"]
                })
            elif "image" in single_media:
                media.append({
                    "type": "photo",
                    "url": single_media["image"]["uri"]
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
                media.append({
                    "type": "photo",
                    "url": media_node["image"]["uri"]
                })

            if media_node.get("__typename") == "Video":
                media.append({
                    "type": "video",
                    "url": media_node.get("playable_url")
                })

    return media


def fetch_posts(limit):
    session = requests.Session()


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

        r = session.post(GRAPHQL_URL, headers=HEADERS, data=payload)

        cleaned_data = parse_fb_response(r.text)
        
        # Save cleaned data for verification
        # with open(f"cleaned_page_{page_num}.json", "w", encoding="utf-8") as f:
        #     json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
        # print(f"Saved cleaned_page_{page_num}.json")
        
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
            post_id = node.get("post_id")
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
                "media": extract_media(node),
            }

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
