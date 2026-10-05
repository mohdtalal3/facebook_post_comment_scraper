"""Page/profile post scraping (posts + media, batched via callback)."""
import json
import time

from . import config
from .config import user_id
from .extractors import (extract_comment_count, extract_page_name,
                         extract_reaction_count, extract_share_count,
                         is_reel_or_video_post, sanitize_name_folder)
from .http import graphql_post, parse_fb_response
from .logging_utils import log
from .media import extract_media
from .resolvers import extract_user_id_from_url
from .storage import post_exists

DOC_ID = "28591463417151325"  # ProfileCometTimelineFeedRefetchQuery


def _headers(referer):
    return {
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.facebook.com",
        "referer": referer,
        "x-fb-friendly-name": "ProfileCometTimelineFeedRefetchQuery",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
    }


def _payload(page_id, cursor, start_date=None, end_date=None):
    variables = {
        "afterTime": start_date,
        "beforeTime": end_date,
        "count": 3, "cursor": cursor,
        "feedLocation": "TIMELINE", "renderLocation": "timeline", "scale": 2,
        "id": page_id,
        "__relay_internal__pv__GHLShouldChangeAdIdFieldNamerelayprovider": True,
        "__relay_internal__pv__GHLShouldChangeSponsoredDataFieldNamerelayprovider": True,
        "__relay_internal__pv__CometFeedStory_enable_reactor_facepilerelayprovider": False,
        "__relay_internal__pv__CometFeedStory_enable_social_bubblesrelayprovider": False,
        "__relay_internal__pv__CometFeedStory_enable_post_permalink_white_space_clickrelayprovider": False,
        "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
        "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
        "__relay_internal__pv__IsWorkUserrelayprovider": False,
        "__relay_internal__pv__TestPilotShouldIncludeDemoAdUseCaserelayprovider": False,
        "__relay_internal__pv__FBReels_deprecate_short_form_video_context_gkrelayprovider": True,
        "__relay_internal__pv__FBReels_enable_view_dubbed_audio_type_gkrelayprovider": True,
        "__relay_internal__pv__CometFeedShareMedia_shouldPrefetchShareImagerelayprovider": False,
        "__relay_internal__pv__CometImmersivePhotoCanUserDisable3DMotionrelayprovider": False,
        "__relay_internal__pv__WorkCometIsEmployeeGKProviderrelayprovider": False,
        "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
        "__relay_internal__pv__FBReelsMediaFooter_comet_enable_reels_ads_gkrelayprovider": True,
        "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
        "__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider": "AUTO_TRANSLATE",
        "__relay_internal__pv__CometUFIShareActionMigrationrelayprovider": True,
        "__relay_internal__pv__CometUFISingleLineUFIrelayprovider": True,
        "__relay_internal__pv__relay_provider_comet_ufi_ssr_seo_deferrelayprovider": True,
        "__relay_internal__pv__CometUFI_dedicated_comment_routable_dialog_gkrelayprovider": True,
        "__relay_internal__pv__ReelsIFUCard_reelsIFULikeCountrelayprovider": False,
        "__relay_internal__pv__FBReelsIFUTileContent_reelsIFUPlayOnHoverrelayprovider": True,
        "__relay_internal__pv__StoriesShouldEnablePhotosensitiveContentWarningrelayprovider": False,
        "__relay_internal__pv__ShouldEnableBakedInTextStoriesrelayprovider": False,
        "__relay_internal__pv__StoriesShouldIncludeFbNotesrelayprovider": True,
    }
    return {
        "av": user_id(),
        "__aaid": "0",
        "__user": user_id(),
        "__a": "1",
        "__comet_req": "15",
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "ProfileCometTimelineFeedRefetchQuery",
        "server_timestamps": "true",
        "fb_dtsg": config.FB_DTSG,
        "doc_id": DOC_ID,
        "variables": json.dumps(variables),
    }


def _story_nodes(cleaned_data):
    """Collect Story nodes from a page-feed response."""
    nodes = []
    timeline_block = None
    for block in cleaned_data:
        if not isinstance(block, dict):
            continue
        node = block.get("node", {})
        typename = node.get("__typename")

        if "timeline_list_feed_units" in node:
            timeline_block = block
            for edge in node["timeline_list_feed_units"].get("edges", []):
                edge_node = edge.get("node")
                if edge_node and edge_node.get("__typename") == "Story":
                    nodes.append(edge_node)
        elif typename == "Story":
            nodes.append(node)
        elif typename == "Group":
            for edge in node.get("group_feed", {}).get("edges", []):
                if edge.get("node", {}).get("__typename") == "Story":
                    nodes.append(edge["node"])
    return nodes, timeline_block


def fetch_posts(page_url, limit=10, min_comments=0, download_images=True,
                batch_size=10, on_batch_complete=None, should_stop=None,
                page_name_state=None, start_date=None, end_date=None):
    """Fetch posts from a page/profile.

    - Resolves the page ID from the URL.
    - Calls `on_batch_complete(batch_posts, total_so_far, limit)` after each batch
      so the caller can fetch comments incrementally.
    - `page_name_state` is a dict {"name": None} shared across calls so the
      page name discovered on the first post is reused.
    - `start_date`/`end_date` are epoch seconds (inclusive) filtering by post time.
    """
    page_id = extract_user_id_from_url(page_url)
    if not page_id:
        return []

    if page_name_state is None:
        page_name_state = {"name": None}

    headers = _headers(f"https://www.facebook.com/profile.php?id={page_id}")
    all_posts, batch_posts = [], []
    cursor, page_num = None, 1
    reached_start = False

    if min_comments > 0:
        log(f"  Filtering posts with at least {min_comments} comments")
    if start_date or end_date:
        log(f"  Date filter: {start_date or 'any'} → {end_date or 'any'}")

    while len(all_posts) < limit and not reached_start:
        if should_stop and should_stop():
            log("  Stop requested — stopping page scrape")
            break

        log(f"  Fetching page {page_num}...")
        cleaned = []
        for attempt in range(3):
            r = graphql_post(_payload(page_id, cursor, start_date, end_date), headers=headers)
            cleaned = parse_fb_response(r.text)
            if cleaned:
                break
            log(f"  Empty response, retrying ({attempt + 1}/3)...")
            time.sleep(2)
        if not cleaned:
            log("  No data received after retries, stopping pagination")
            break

        nodes, timeline_block = _story_nodes(cleaned)
        log(f"  Found {len(nodes)} posts on page {page_num}")

        for node in nodes:
            if should_stop and should_stop():
                break
            if is_reel_or_video_post(node):
                log("  Skipping reel/video post")
                continue

            # Date filter: feed is newest-first, so once we pass the start
            # date everything after is older — stop paginating.
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

            if not page_name_state["name"]:
                page_name_state["name"] = extract_page_name(node)
                if page_name_state["name"]:
                    log(f"  Page name: {page_name_state['name']}")

            post_id = node.get("post_id")
            if not post_id:
                continue

            name_folder = sanitize_name_folder(page_name_state["name"]) or "Unknown"
            if post_exists("page_post", name_folder, post_id):
                log(f"  Skipping already scraped post: {post_id}")
                continue

            try:
                permalink = node["attachments"][0]["styles"]["attachment"]["url"]
            except Exception:
                permalink = None
            if not permalink:
                permalink = f"https://www.facebook.com/{post_id}"

            media_dir = f"page_post/{name_folder}"
            post = {
                "post_id": post_id,
                "feedback_id": node.get("feedback", {}).get("id"),
                "created_at": node.get("creation_time"),
                "text": (node.get("comet_sections", {})
                             .get("content", {}).get("story", {})
                             .get("message", {}).get("text")),
                "permalink": permalink,
                "comment_count": comment_count,
                "reaction_count": extract_reaction_count(node),
                "share_count": extract_share_count(node),
                "page_name": page_name_state["name"],
                "media": extract_media(node, post_id, media_dir, download_images),
            }

            batch_posts.append(post)
            all_posts.append(post)

            if batch_size > 0 and len(batch_posts) >= batch_size and on_batch_complete:
                log(f"  Batch complete: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
                on_batch_complete(batch_posts, len(all_posts), limit)
                batch_posts = []

            if len(all_posts) >= limit:
                break

        page_info = None
        if timeline_block:
            page_info = ((timeline_block["node"].get("timeline_list_feed_units") or {})
                         .get("page_info"))
        if not page_info:
            page_info = next((b["page_info"] for b in cleaned
                              if isinstance(b, dict) and "page_info" in b), None)

        cursor = (page_info or {}).get("end_cursor")
        if not cursor or len(all_posts) >= limit:
            break

        time.sleep(1)
        page_num += 1

    if batch_posts and on_batch_complete:
        log(f"  Final batch: {len(batch_posts)} posts. Total: {len(all_posts)}/{limit}")
        on_batch_complete(batch_posts, len(all_posts), limit)

    return all_posts
