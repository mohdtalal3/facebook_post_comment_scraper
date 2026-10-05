"""Storage layer: everything under the project's data/ directory.

Layout:
    data/simple_post/{post_id}/{post_id}.json
    data/page_post/{page_name}/{post_id}/{post_id}.json
    data/group_post/{group_name}/{post_id}/{post_id}.json
"""
import io
import json
import os
import shutil
import zipfile

from .logging_utils import log

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

POST_TYPES = ("simple_post", "page_post", "group_post")


def post_dir(post_type, name_folder, post_id):
    if post_type == "simple_post":
        return os.path.join(DATA_DIR, "simple_post", str(post_id))
    return os.path.join(DATA_DIR, post_type, name_folder or "Unknown", str(post_id))


def post_file(post_type, name_folder, post_id):
    return os.path.join(post_dir(post_type, name_folder, post_id), f"{post_id}.json")


def post_exists(post_type, name_folder, post_id):
    if not post_id:
        return False
    return os.path.exists(post_file(post_type, name_folder, post_id))


def save_post_data(post_type, post_id, post_data, comments_data):
    """Save post + comments combined as {post_id}.json. Returns the file path."""
    name = post_data.get("page_name") or post_data.get("group_name")
    folder = post_dir(post_type, name, post_id)
    os.makedirs(folder, exist_ok=True)

    path = post_file(post_type, name, post_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({**post_data, "comments": comments_data}, f, ensure_ascii=False, indent=2)

    log(f"  Saved to {os.path.relpath(path, PROJECT_ROOT)}")
    return path


def load_post(post_type, name_folder, post_id):
    path = post_file(post_type, name_folder, post_id)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def delete_post(post_type, name_folder, post_id):
    folder = post_dir(post_type, name_folder, post_id)
    if os.path.isdir(folder):
        shutil.rmtree(folder)
        return True
    return False


def images_zip(post_type, name_folder, post_id):
    """Zip all images in a post folder. Returns (zip_bytes, filename) or None."""
    folder = post_dir(post_type, name_folder, post_id)
    if not os.path.isdir(folder):
        return None

    images = [f for f in os.listdir(folder)
              if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))]
    if not images:
        return None

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            zf.write(os.path.join(folder, img), arcname=img)
    buf.seek(0)
    return buf.getvalue(), f"{post_id}_images.zip"


def _iter_post_files():
    """Yield (post_type, name_folder, post_id, json_path) for every saved post."""
    if not os.path.isdir(DATA_DIR):
        return
    for post_type in POST_TYPES:
        type_dir = os.path.join(DATA_DIR, post_type)
        if not os.path.isdir(type_dir):
            continue
        for source_name in sorted(os.listdir(type_dir)):
            source_dir = os.path.join(type_dir, source_name)
            if not os.path.isdir(source_dir):
                continue
            # simple_post has no name folder level
            candidates = [(source_name, source_dir)] if post_type == "simple_post" else [
                (d, os.path.join(source_dir, d)) for d in sorted(os.listdir(source_dir))
            ]
            for post_id, post_folder in candidates:
                if not os.path.isdir(post_folder):
                    continue
                json_path = os.path.join(post_folder, f"{post_id}.json")
                if os.path.exists(json_path):
                    yield post_type, source_name, post_id, json_path


def list_posts(post_type=None, source=None, query=None, min_comments=0):
    """List all scraped posts with metadata for the posts browser."""
    results = []
    for p_type, source_name, post_id, json_path in _iter_post_files():
        if post_type and p_type != post_type:
            continue
        if source and source_name != source:
            continue

        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        text = data.get("text") or ""
        if query and query.lower() not in text.lower() and query not in post_id:
            continue

        comment_count = data.get("comment_count") or 0
        try:
            comment_count = int(comment_count)
        except (TypeError, ValueError):
            comment_count = 0
        if min_comments and comment_count < min_comments:
            continue

        folder = os.path.dirname(json_path)
        images = [f for f in os.listdir(folder)
                  if f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))]

        comments = data.get("comments") or []
        results.append({
            "post_type": p_type,
            "source": None if p_type == "simple_post" else source_name,
            "post_id": post_id,
            "text": text[:300],
            "comment_count": comment_count,
            "reaction_count": data.get("reaction_count"),
            "share_count": data.get("share_count"),
            "scraped_comments": len(comments),
            "image_count": len(images),
            "permalink": data.get("permalink"),
            "saved_at": int(os.path.getmtime(json_path)),
            "file": os.path.relpath(json_path, PROJECT_ROOT),
        })

    results.sort(key=lambda p: p["saved_at"], reverse=True)
    return results


def list_sources():
    """Distinct page/group names that have scraped data."""
    sources = {}
    for p_type, source_name, _, _ in _iter_post_files():
        if p_type == "simple_post":
            continue
        sources.setdefault(source_name, {"post_type": p_type, "name": source_name})
    return sorted(sources.values(), key=lambda s: s["name"].lower())
