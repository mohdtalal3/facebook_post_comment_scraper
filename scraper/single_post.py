"""Single post scraping: comments + optional album image download."""
from .comments import fetch_comments_for_post
from .logging_utils import log
from .media import fetch_album_images
from .resolvers import extract_post_id_from_url
from .storage import save_post_data


def scrape_single_post(post_url, download_images=True, should_stop=None):
    """Scrape one post (from URL or raw ID): comments, replies and images.

    Returns the post_id that was scraped, or None if it could not be resolved.
    """
    post_id = post_url.strip()
    if post_id.startswith("http"):
        post_id = extract_post_id_from_url(post_id)
    if not post_id:
        log("  Could not extract post ID")
        return None

    log(f"  Post ID: {post_id}")

    comments, post_info = fetch_comments_for_post(post_id, should_stop=should_stop)

    post_data = {
        "post_id": post_id,
        "type": "simple_post",
        "post_info": post_info,
    }
    if post_info:
        if post_info.get("reaction_count"):
            post_data["reaction_count"] = post_info["reaction_count"]
        if post_info.get("share_count"):
            post_data["share_count"] = post_info["share_count"]
    save_post_data("simple_post", post_id, post_data, comments)

    if download_images and post_info and post_info.get("media_id"):
        log(f"  Fetching album images for media {post_info['media_id']}...")
        try:
            from .storage import post_dir
            fetch_album_images(post_info["media_id"], post_id,
                               save_dir=post_dir("simple_post", None, post_id))
        except Exception as e:
            log(f"  Error fetching images: {e}")
    elif not download_images:
        log("  Image downloading is off — skipping album images")

    return post_id
