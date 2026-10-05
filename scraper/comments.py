"""Comment and reply scraping with full metadata (author, IDs, reactions)."""
import json

from . import config
from .config import user_id
from .http import fb_json, graphql_post
from .logging_utils import log
from .resolvers import convert_post_id_to_feedback_id

COMMENTS_DOC_ID = "27806180149070312"  # CommentsListComponentsPaginationQuery
REPLIES_DOC_ID = "26570577339199586"   # Depth1CommentsListPaginationQuery


def _author_info(node):
    """Extract author name / id / profile url from a comment or reply node."""
    author = node.get("author") or {}
    return {
        "author": author.get("name"),
        "author_id": author.get("id"),
        "author_url": author.get("url"),
    }


def _comments_payload(feedback_id, cursor=None):
    return {
        "av": user_id(),
        "__user": user_id(),
        "__a": "1",
        "fb_dtsg": config.FB_DTSG,
        "fb_api_caller_class": "RelayModern",
        "server_timestamps": "true",
        "doc_id": COMMENTS_DOC_ID,
        "variables": json.dumps({
            "commentsAfterCount": -1,
            "commentsAfterCursor": cursor,
            "commentsBeforeCount": None,
            "commentsBeforeCursor": None,
            "commentsIntentToken": None,
            "feedLocation": "POST_PERMALINK_DIALOG",
            "focusCommentID": None,
            "scale": 2,
            "useDefaultActor": False,
            "id": feedback_id,
            "__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider": "AUTO_TRANSLATE",
            "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
            "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
            "__relay_internal__pv__IsWorkUserrelayprovider": False,
        }),
    }


def _replies_payload(comment_feedback_id, expansion_token):
    return {
        "av": user_id(),
        "__user": user_id(),
        "__a": "1",
        "fb_dtsg": config.FB_DTSG,
        "fb_api_caller_class": "RelayModern",
        "server_timestamps": "true",
        "doc_id": REPLIES_DOC_ID,
        "variables": json.dumps({
            "clientKey": None,
            "expansionToken": expansion_token,
            "feedLocation": "POST_PERMALINK_DIALOG",
            "focusCommentID": None,
            "scale": 2,
            "useDefaultActor": False,
            "id": comment_feedback_id,
            "__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider": "AUTO_TRANSLATE",
            "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
            "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
            "__relay_internal__pv__IsWorkUserrelayprovider": False,
        }),
    }


def _parse_comment(node):
    """Map a raw comment/reply node into our output shape."""
    feedback = node.get("feedback") or {}
    return {
        "comment_id": node.get("legacy_fbid"),
        **_author_info(node),
        "text": (node.get("body") or {}).get("text", ""),
        "reaction_count": feedback.get("reactors", {}).get("count_reduced", "0"),
        "_feedback_id": feedback.get("id"),
        "_expansion_token": (feedback.get("expansion_info") or {}).get("expansion_token"),
    }


def fetch_comments(feedback_id):
    """Fetch all top-level comments for a feedback ID.

    Returns (comments, post_info) where post_info carries the parent post
    story/media IDs extracted from the first response.
    """
    results = []
    cursor = None
    post_info = None

    while True:
        r = graphql_post(
            _comments_payload(feedback_id, cursor),
            headers={"x-fb-friendly-name": "CommentsListComponentsPaginationQuery"},
        )
        j = fb_json(r.text)

        node = j.get("data", {}).get("node", {}) or {}
        comments_block = ((node.get("comment_rendering_instance_for_feed_location") or {})
                              .get("comments") or {})
        edges = comments_block.get("edges") or []
        if not edges:
            break

        for e in edges:
            n = e["node"]

            if post_info is None:
                post_info = _extract_post_info(n)

            results.append(_parse_comment(n))

        cursor = comments_block.get("page_info", {}).get("end_cursor")
        if not cursor:
            break

    return results, post_info


def _extract_post_info(node):
    """Pull parent post story/media IDs out of the first comment response."""
    parent = (node.get("comet_comment_author_name_and_badges_renderer", {})
                  .get("comment", {})
                  .get("parent_post_story", {})) or node.get("parent_post_story", {})
    if not parent:
        return None

    info = {"post_story_id": parent.get("id"), "media_id": None}
    for attachment in parent.get("attachments", []):
        media = attachment.get("media", {})
        if media and media.get("id"):
            info["media_id"] = media.get("id")
            break

    log(f"  Extracted post info: {info}")
    return info


def fetch_replies(comment):
    """Fetch all replies for a single comment (must contain _feedback_id/_expansion_token)."""
    r = graphql_post(
        _replies_payload(comment["_feedback_id"], comment["_expansion_token"]),
        headers={"x-fb-friendly-name": "Depth1CommentsListPaginationQuery"},
    )
    j = fb_json(r.text)

    edges = (((j.get("data", {}).get("node") or {})
              .get("replies_connection") or {})
             .get("edges") or [])

    return [_parse_comment(e["node"]) for e in edges]


def fetch_comments_for_post(post_id, should_stop=None):
    """Fetch all comments + nested replies for a post ID, ready for saving."""
    feedback_id = convert_post_id_to_feedback_id(post_id)
    log(f"  Fetching comments for post {post_id}...")

    comments, post_info = fetch_comments(feedback_id)

    all_data = []
    for c in comments:
        if should_stop and should_stop():
            log("  Stop requested — returning comments collected so far")
            break

        log(f"    {c.get('author') or 'Unknown'}: {(c.get('text') or '')[:60]}")
        replies = []
        if c.get("_expansion_token"):
            try:
                replies = fetch_replies(c)
                for r in replies:
                    log(f"      {r.get('author') or 'Unknown'}: {(r.get('text') or '')[:60]}")
            except Exception as e:
                log(f"      Failed to fetch replies: {e}")

        all_data.append({k: v for k, v in {**c, "replies": replies}.items()
                         if not k.startswith("_")})

    log(f"  Found {len(all_data)} comments")
    return all_data, post_info
