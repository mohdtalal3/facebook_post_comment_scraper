"""Media extraction and image downloading (with optional album traversal)."""
import json
import os
import time

import requests

from .config import COOKIES, FB_DTSG, PROXIES, user_id
from .http import graphql_post, parse_fb_response
from .logging_utils import log

PHOTO_DOC_ID = "26168653472729001"  # CometPhotoRootContentQuery
PHOTO_HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "x-fb-friendly-name": "CometPhotoRootContentQuery",
}


def download_image(url, save_dir, post_id, image_index=1, max_retries=3):
    """Download an image as {post_id}.jpg / {post_id}_2.jpg ... Returns filename or None."""
    if not url or not post_id:
        return None

    os.makedirs(save_dir, exist_ok=True)

    ext = ".jpg"
    if ".png" in url.lower():
        ext = ".png"
    elif ".jpeg" in url.lower():
        ext = ".jpeg"

    filename = f"{post_id}{ext}" if image_index == 1 else f"{post_id}_{image_index}{ext}"
    path = os.path.join(save_dir, filename)

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, proxies=PROXIES, timeout=30)
            r.raise_for_status()
            with open(path, "wb") as f:
                f.write(r.content)
            log(f"  Downloaded image: {filename}")
            return filename
        except Exception as e:
            log(f"  Download attempt {attempt}/{max_retries} failed: {e}")
            if attempt < max_retries:
                time.sleep(attempt * 2)

    log(f"  Failed to download image after {max_retries} attempts")
    return None


def fetch_remaining_images(last_media_id, post_id, current_image_count, save_dir):
    """Traverse the photo viewer for albums with more than 5 images."""
    if not last_media_id or not post_id:
        return []

    log(f"  Fetching remaining images after image #{current_image_count}...")

    remaining = []
    current_node = last_media_id
    visited = set()
    image_index = current_image_count

    while current_node and current_node not in visited and image_index <= 50:
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
            "shouldShowComments": True,
        }
        payload = {
            "av": user_id(),
            "__user": user_id(),
            "__a": "1",
            "fb_dtsg": FB_DTSG,
            "doc_id": PHOTO_DOC_ID,
            "variables": json.dumps(variables),
        }

        try:
            r = graphql_post(payload, headers=PHOTO_HEADERS)
            blocks = parse_fb_response(r.text)
            if not blocks:
                break

            image_url = next((b["currMedia"].get("image", {}).get("uri")
                              for b in blocks if "currMedia" in b), None)
            if image_url:
                image_index += 1
                saved = download_image(image_url, save_dir, post_id, image_index)
                remaining.append({"type": "photo", "url": image_url, "saved_as": saved})

            next_node = next((b["nextMediaAfterNodeId"].get("id")
                              for b in blocks
                              if b.get("nextMediaAfterNodeId") and b["nextMediaAfterNodeId"].get("id")), None)
            if not next_node:
                break
            current_node = next_node
            time.sleep(0.5)
        except Exception as e:
            log(f"  Error fetching next image: {e}")
            break

    if remaining:
        log(f"  Fetched {len(remaining)} additional images")
    return remaining


def extract_media(node, post_id, save_dir, download_images=True):
    """Extract photo/video media from a Story node.

    Returns a list of media dicts: {type: photo|video, url, saved_as?}.
    Photos are downloaded when `download_images` is True.
    """
    media = []
    image_index = 0
    last_media_id = None

    def add_photo(url, media_node):
        nonlocal image_index, last_media_id
        image_index += 1
        last_media_id = media_node.get("id")
        saved = download_image(url, save_dir, post_id, image_index) if download_images else None
        media.append({"type": "photo", "url": url, "saved_as": saved})

    for att in node.get("attachments") or []:
        styles = att.get("styles") or {}
        attachment = styles.get("attachment") or {}
        single = attachment.get("media") or {}

        if single:
            if "photo_image" in single:
                add_photo(single["photo_image"]["uri"], single)
            elif "image" in single:
                add_photo(single["image"]["uri"], single)
            if single.get("__typename") == "Video":
                media.append({"type": "video", "url": single.get("playable_url")})

        for sub in att.get("all_subattachments", {}).get("nodes", []):
            m = sub.get("media") or {}
            if "image" in m:
                add_photo(m["image"]["uri"], m)
            if m.get("__typename") == "Video":
                media.append({"type": "video", "url": m.get("playable_url")})

    if download_images and image_index == 5 and last_media_id:
        media.extend(fetch_remaining_images(last_media_id, post_id, image_index, save_dir))

    return media


def fetch_album_images(start_media_id, post_id, save_dir, cookies=None):
    """Traverse a single post's album from a media ID, downloading every image."""
    current_node = start_media_id
    visited = set()
    count = 0

    while current_node and current_node not in visited:
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
            "shouldShowComments": True,
        }
        payload = {
            "av": user_id(),
            "__user": user_id(),
            "__a": "1",
            "fb_dtsg": FB_DTSG,
            "doc_id": PHOTO_DOC_ID,
            "variables": json.dumps(variables),
        }

        r = graphql_post(payload, headers=PHOTO_HEADERS)
        blocks = parse_fb_response(r.text)
        if not blocks:
            break

        image_url = next((b["currMedia"].get("image", {}).get("uri")
                          for b in blocks if "currMedia" in b), None)
        if image_url:
            count += 1
            if download_image(image_url, save_dir, post_id, count):
                log(f"    Downloaded {count} image(s) so far")

        next_node = next((b["nextMediaAfterNodeId"].get("id")
                          for b in blocks
                          if b.get("nextMediaAfterNodeId") and b["nextMediaAfterNodeId"].get("id")), None)
        if not next_node:
            break
        current_node = next_node

    log(f"  Album traversal complete: {count} image(s)")
    return count
