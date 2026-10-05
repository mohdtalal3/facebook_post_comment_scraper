"""Group post scraping (posts + media, batched via callback)."""
import json
import time

from . import config
from .config import user_id
from .extractors import (extract_comment_count, extract_group_name,
                         extract_reaction_count, extract_share_count,
                         is_reel_or_video_post, sanitize_name_folder)
from .http import graphql_post, parse_fb_response
from .logging_utils import log
from .media import extract_media
from .resolvers import extract_group_id_from_url
from .storage import post_exists

DOC_ID = "25716860671307636"  # GroupsCometFeedRegularStoriesPaginationQuery


def _headers(group_id):
    return {
        "user-agent": "Mozilla/5.0",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.facebook.com",
        "referer": f"https://www.facebook.com/groups/{group_id}/",
    }


def _payload(group_id, cursor):
    variables = {
        "count": 3, "cursor": cursor, "feedLocation": "GROUP",
        "feedType": "DISCUSSION", "feedbackSource": 0, "filterTopicId": None,
        "focusCommentID": None, "privacySelectorRenderLocation": "COMET_STREAM",
        "renderLocation": "group", "scale": 2, "stream_initial_count": 1,
        "useDefaultActor": False, "id": group_id,
    }
    return {
        "av": user_id(),
        "__user": user_id(),
        "__a": "1",
        "fb_dtsg": config.FB_DTSG,
        "doc_id": DOC_ID,
        "variables": json.dumps(variables),
    }


def _story_nodes(item):
    node = item.get("node", {})
    typename = node.get("__typename")
    if typename == "Story":
        return [node]
    if typename == "Group":
        return [e.get("node", {}) for e in node.get("group_feed", {}).get("edges", [])
                if e.get("node", {}).get("__typename") == "Story"]
    return []


def fetch_posts(group_url, limit=10, min_comments=0, download_images=True,
                batch_size=10, on_batch_complete=None, should_stop=None,
                group_name_state=None, start_date=None, end_date=None):
    """Fetch posts from a Facebook group. Same batching contract as page_posts.

    `start_date`/`end_date` are epoch seconds (inclusive) filtering by post time.
    """
    group_id = extract_group_id_from_url(group_url)
    if not group_id:
        return []

    if group_name_state is None:
        group_name_state = {"name": None}

    headers = _headers(group_id)
    all_posts, batch_posts = [], []
    cursor, page_num = None, 1
    reached_start = False

    if min_comments > 0:
        log(f"  Filtering posts with at least {min_comments} comments")
    if start_date or end_date:
        log(f"  Date filter: {start_date or 'any'} → {end_date or 'any'}")

    while len(all_posts) < limit and not reached_start:
        if should_stop and should_stop():
            log("  Stop requested — stopping group scrape")
            break

        log(f"  Fetching page {page_num}...")
        cleaned = []
        for attempt in range(3):
            r = graphql_post(_payload(group_id, cursor), headers=headers)
            cleaned = parse_fb_response(r.text)
            if cleaned:
                break
            log(f"  Empty response, retrying ({attempt + 1}/3)...")
            time.sleep(2)
        if not cleaned:
            log("  No data received after retries, stopping pagination")
            break

        posts_found = 0
        next_cursor = None

        for item in cleaned:
            if not isinstance(item, dict):
                continue

            for node in _story_nodes(item):
                if should_stop and should_stop():
                    break
                if is_reel_or_video_post(node):
                    log("  Skipping reel/video post")
                    continue

                # Date filter: feed is newest-first, so once we pass the
                # start date everything after is older — stop paginating.
                created = node.get("creation_time")
                if end_date and created and created > end_date:
                    log("  Skipping post newer than end date")
                    continue
                if start_date and created and created < start_date:
                    log("  Reached posts older than start date — stopping")
                    reached_start = True
                    break

                comment_count = extract_comment_count(node)
                if min_comments > 0 and comment_count < min_comments:
                    log(f"  Skipping post with {comment_count} comments (need {min_comments}+)")
                    continue

                if not group_name_state["name"]:
                    group_name_state["name"] = extract_group_name(node)
                    if group_name_state["name"]:
                        log(f"  Group name: {group_name_state['name']}")

                post_id = node.get("post_id")
                if not post_id:
                    continue

                name_folder = sanitize_name_folder(group_name_state["name"]) or "Unknown"
                if post_exists("group_post", name_folder, post_id):
                    log(f"  Skipping already scraped post: {post_id}")
                    continue

                content_story = (node.get("comet_sections", {})
                                     .get("content", {}).get("story", {}))
                media_dir = f"group_post/{name_folder}"
                media = extract_media(node, post_id, media_dir, download_images)

                post = {
                    "id": node.get("id"),
                    "post_id": post_id,
                    "created_at": node.get("creation_time"),
                    "text": (content_story.get("message", {}) or {}).get("text", ""),
                    "comment_count": comment_count,
                    "reaction_count": extract_reaction_count(node),
                    "share_count": extract_share_count(node),
                    "group_name": group_name_state["name"],
                    "permalink": node.get("permalink_url") or f"https://www.facebook.com/{post_id}",
                    "media": media,
                }

                batch_posts.append(post)
                all_posts.append(post)
                posts_found += 1
                log(f"  Found post: {post_id}")

                if batch_size > 0 and len(batch_posts) >= batch_size and on_batch_complete:
                    log(f"  Batch complete: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
                    on_batch_complete(batch_posts, len(all_posts), limit)
                    batch_posts = []

                if len(all_posts) >= limit:
                    break

            if len(all_posts) >= limit:
                break

            page_info = item.get("page_info")
            if page_info and page_info.get("has_next_page"):
                next_cursor = page_info.get("end_cursor")

        log(f"  Found {posts_found} posts on this page")

        if not next_cursor or len(all_posts) >= limit:
            break

        cursor = next_cursor
        page_num += 1
        time.sleep(2)

    if batch_posts and on_batch_complete:
        log(f"  Final batch: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
        on_batch_complete(batch_posts, len(all_posts), limit)

    return all_posts
