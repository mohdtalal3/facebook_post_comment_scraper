"""Comment and reply scraping with full metadata (author, IDs, reactions)."""
import base64
import json

from . import config
from .config import user_id, COOKIES
from .http import fb_json, graphql_post
from .logging_utils import log

# doc_id for CometSinglePostDialogContentQuery (first page of comments, uses storyID)
DIALOG_DOC_ID = "40786070794317455"
# doc_id for CommentsListComponentsPaginationQuery (subsequent pages, uses feedback id)
PAGINATION_DOC_ID = "27806180149070312"
REPLIES_DOC_ID = "26570577339199586"   # Depth1CommentsListPaginationQuery


def build_story_id(post_id):
    """Build the base64-encoded storyID from a post id.
    Format: S:_I<uid>:<post_id>:<post_id>
    Uses the viewer's c_user when available, otherwise the post id itself."""
    uid = COOKIES.get("c_user") or post_id
    raw = f"S:_I{uid}:{post_id}:{post_id}"
    return base64.b64encode(raw.encode()).decode()


def normalize_story_id(story_id):
    """Accept an encoded storyID, an old-style feedback id, or a raw post id
    and return the encoded storyID needed by the dialog query."""
    try:
        decoded = base64.b64decode(story_id).decode("utf-8")
    except Exception:
        decoded = story_id

    if decoded.startswith("S:_I"):
        return story_id  # already a storyID

    if decoded.startswith("feedback:"):
        post_id = decoded.split(":", 1)[1]
    elif decoded.isdigit():
        post_id = decoded
    else:
        raise ValueError(f"Cannot determine post id from: {story_id}")

    return build_story_id(post_id)


def _author_info(node):
    """Extract author name / id / profile url from a comment or reply node."""
    author = node.get("author") or {}
    return {
        "author": author.get("name"),
        "author_id": author.get("id"),
        "author_url": author.get("url"),
    }


def _dialog_payload(story_id):
    return {
        "av": user_id(),
        "__aaid": "0",
        "__user": user_id(),
        "__a": "1",
        "__comet_req": "15",
        "fb_dtsg": config.FB_DTSG,
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "CometSinglePostDialogContentQuery",
        "server_timestamps": "true",
        "doc_id": DIALOG_DOC_ID,
        "variables": json.dumps({
            "feedbackSource": 2,
            "feedLocation": "POST_PERMALINK_DIALOG",
            "focusCommentID": None,
            "privacySelectorRenderLocation": "COMET_STREAM",
            "renderLocation": "permalink",
            "scale": 2,
            "shouldChangeNodeFieldName": True,
            "storyID": story_id,
            "useDefaultActor": False,
            "__relay_internal__pv__CometSinglePostDialogContent_isFloatingCTAEnabledrelayprovider": False,
            "__relay_internal__pv__GHLShouldChangeAdIdFieldNamerelayprovider": True,
            "__relay_internal__pv__GHLShouldChangeSponsoredDataFieldNamerelayprovider": True,
            "__relay_internal__pv__CometFeedStory_enable_reactor_facepilerelayprovider": False,
            "__relay_internal__pv__CometFeedStory_enable_social_bubblesrelayprovider": False,
            "__relay_internal__pv__CometFeedStory_enable_post_permalink_white_space_clickrelayprovider": False,
            "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
            "__relay_internal__pv__IsWorkUserrelayprovider": False,
            "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
            "__relay_internal__pv__CometUFICommentActionLinkStableIDsrelayprovider": False,
            "__relay_internal__pv__TestPilotShouldIncludeDemoAdUseCaserelayprovider": False,
            "__relay_internal__pv__FBReels_deprecate_short_form_video_context_gkrelayprovider": True,
            "__relay_internal__pv__CometUFI_dedicated_comment_routable_dialog_gkrelayprovider": True,
            "__relay_internal__pv__FBReels_enable_view_dubbed_audio_type_gkrelayprovider": True,
            "__relay_internal__pv__CometFeedShareMedia_shouldPrefetchShareImagerelayprovider": True,
            "__relay_internal__pv__CometImmersivePhotoCanUserDisable3DMotionrelayprovider": False,
            "__relay_internal__pv__WorkCometIsEmployeeGKProviderrelayprovider": False,
            "__relay_internal__pv__IsMergQAPollsrelayprovider": False,
            "__relay_internal__pv__FBReelsMediaFooter_comet_enable_reels_ads_gkrelayprovider": True,
            "__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider": False,
            "__relay_internal__pv__GeminiUFISaveToKnowledgeHubGKrelayprovider": False,
            "__relay_internal__pv__CometUFIShareActionMigrationrelayprovider": True,
            "__relay_internal__pv__CometUFISingleLineUFIrelayprovider": True,
            "__relay_internal__pv__relay_provider_comet_ufi_ssr_seo_deferrelayprovider": True,
            "__relay_internal__pv__FBReelsIFUTileContent_reelsIFUPlayOnHoverrelayprovider": True,
            "__relay_internal__pv__StoriesShouldEnablePhotosensitiveContentWarningrelayprovider": True,
            "__relay_internal__pv__ShouldEnableBakedInTextStoriesrelayprovider": True,
            "__relay_internal__pv__StoriesShouldIncludeFbNotesrelayprovider": True,
            "__relay_internal__pv__ProfileCometSeoIsViewerLoggedOutrelayprovider": False
        }),
    }


def _pagination_payload(feedback_id, cursor=None):
    return {
        "av": user_id(),
        "__user": user_id(),
        "__a": "1",
        "fb_dtsg": config.FB_DTSG,
        "fb_api_caller_class": "RelayModern",
        "server_timestamps": "true",
        "doc_id": PAGINATION_DOC_ID,
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
        "reaction_count": (feedback.get("reactors") or {}).get("count_reduced", "0"),
        "_feedback_id": feedback.get("id"),
        "_expansion_token": (feedback.get("expansion_info") or {}).get("expansion_token"),
    }


def _parse_dialog_comments(j):
    """Extract the comments block from a CometSinglePostDialogContentQuery response."""
    data = j.get("data") or {}
    node_v2 = data.get("node_v2") or {}
    comet_sections = node_v2.get("comet_sections") or {}
    feedback = comet_sections.get("feedback") or {}
    story = feedback.get("story") or {}
    ufi_container = story.get("story_ufi_container") or {}
    ufi_story = ufi_container.get("story") or {}
    feedback_context = ufi_story.get("feedback_context") or {}
    target = feedback_context.get("feedback_target_with_context") or {}
    renderer = target.get("comment_list_renderer") or {}
    fb = renderer.get("feedback") or {}
    instance = fb.get("comment_rendering_instance_for_feed_location") or {}
    return instance.get("comments") or {}


def _parse_pagination_comments(j):
    """Extract the comments block from a CommentsListComponentsPaginationQuery response."""
    data = j.get("data") or {}
    node = data.get("node") or {}
    rendering = node.get("comment_rendering_instance_for_feed_location") or {}
    return rendering.get("comments") or {}


def _collect_comments(comments_block, results):
    edges = comments_block.get("edges") or []
    if not edges:
        return False

    for e in edges:
        parsed = _parse_comment((e or {}).get("node") or {})
        # Drop junk entries — an edge with no text AND no feedback id is an
        # empty/malformed node, not a real comment.
        if parsed["text"] or parsed["_feedback_id"]:
            results.append(parsed)

    page_info = comments_block.get("page_info") or {}
    return bool(page_info.get("end_cursor"))


def _extract_post_info_from_story(node_v2):
    """Extract post story id, media id and counts from the dialog response story node."""
    try:
        info = {"post_story_id": node_v2.get("id"), "media_id": None}
        for attachment in node_v2.get("attachments") or []:
            media = (attachment or {}).get("media") or {}
            if media.get("id"):
                info["media_id"] = media.get("id")
                break

        from .extractors import extract_reaction_count, extract_share_count
        reaction_count = extract_reaction_count(node_v2)
        share_count = extract_share_count(node_v2)
        if reaction_count:
            info["reaction_count"] = reaction_count
        if share_count:
            info["share_count"] = share_count

        log(f"  Extracted post info: {info}")
        return info
    except Exception as e:
        log(f"  Could not extract post info: {e}")
        return None


def fetch_comments(post_id):
    """Fetch all top-level comments for a post/story/feedback ID.

    First page uses CometSinglePostDialogContentQuery (storyID based); the real
    feedback id extracted from that response drives subsequent pagination pages.

    Returns (comments, post_info) where post_info carries the parent post
    story/media IDs extracted from the first response.
    """
    results = []
    post_info = None
    feedback_id = None
    cursor = None
    has_more = True

    story_id = normalize_story_id(post_id)

    while has_more:
        if feedback_id is None:
            # First page: CometSinglePostDialogContentQuery (storyID based)
            r = graphql_post(
                _dialog_payload(story_id),
                headers={"x-fb-friendly-name": "CometSinglePostDialogContentQuery"},
            )
        else:
            # Subsequent pages: pagination query (real feedback id + cursor)
            r = graphql_post(
                _pagination_payload(feedback_id, cursor),
                headers={"x-fb-friendly-name": "CommentsListComponentsPaginationQuery"},
            )
        j = fb_json(r.text)

        if feedback_id is None:
            data = j.get("data") or {}
            node_v2 = data.get("node_v2") or {}
            if node_v2:
                # Real (pfbid-based) feedback id needed for pagination + post info
                story = ((node_v2.get("comet_sections") or {})
                         .get("content") or {})
                feedback_id = ((story.get("story") or {})
                               .get("feedback") or {}).get("id")
                if post_info is None:
                    post_info = _extract_post_info_from_story(node_v2)
            comments_block = _parse_dialog_comments(j)
        else:
            comments_block = _parse_pagination_comments(j)

        has_more = _collect_comments(comments_block, results)
        cursor = (comments_block.get("page_info") or {}).get("end_cursor")

        if not feedback_id or not cursor:
            has_more = False

    return results, post_info


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
    log(f"  Fetching comments for post {post_id}...")

    comments, post_info = fetch_comments(post_id)

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
