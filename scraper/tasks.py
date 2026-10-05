"""High-level scrape operations used by the web app (and usable from CLI)."""
from . import config
from .config import apply_proxy, set_session
from .logging_utils import log, set_sink, clear_sink


def _init_session(cookies, fb_dtsg):
    """Use the explicitly passed session, or keep whatever Settings configured."""
    if cookies is not None or fb_dtsg is not None:
        set_session(cookies, fb_dtsg)
    apply_proxy(bool(config.COOKIES), log=log)


def run_simple_post(urls, cookies=None, fb_dtsg=None, download_images=True, should_stop=None):
    """Scrape one or more single posts. Returns list of scraped post IDs."""
    _init_session(cookies, fb_dtsg)

    scraped = []
    for i, url in enumerate(urls, 1):
        if should_stop and should_stop():
            log("Stop requested — halting")
            break
        log(f"\n[{i}/{len(urls)}] Processing: {url}")
        from .single_post import scrape_single_post
        post_id = scrape_single_post(url, download_images=download_images, should_stop=should_stop)
        if post_id:
            scraped.append(post_id)
        import time
        time.sleep(1)
    return scraped


def run_page_posts(urls, limit=10, min_comments=0, cookies=None, fb_dtsg=None,
                   download_images=True, should_stop=None,
                   start_date=None, end_date=None):
    """Scrape posts + comments from one or more pages."""
    _init_session(cookies, fb_dtsg)

    from .page_posts import fetch_posts
    from .comments import fetch_comments_for_post
    from .storage import save_post_data

    total_scraped = 0
    for i, url in enumerate(urls, 1):
        if should_stop and should_stop():
            log("Stop requested — halting")
            break

        log(f"\n[Page {i}/{len(urls)}] {url}")
        name_state = {"name": None}

        def process_batch(batch_posts, total_so_far, total_limit):
            nonlocal total_scraped
            for post in batch_posts:
                if should_stop and should_stop():
                    break
                post_id = post.get("post_id")
                if not post_id:
                    continue
                log(f"  Processing post {post_id}...")
                try:
                    comments, _ = fetch_comments_for_post(post_id, should_stop=should_stop)
                    save_post_data("page_post", post_id, post, comments)
                except Exception as e:
                    log(f"  Error fetching comments: {e} — saving post without comments")
                    save_post_data("page_post", post_id, post, [])
                total_scraped += 1
                import time
                time.sleep(1)

        fetch_posts(url, limit=limit, min_comments=min_comments,
                    download_images=download_images, batch_size=2,
                    on_batch_complete=process_batch, should_stop=should_stop,
                    page_name_state=name_state,
                    start_date=start_date, end_date=end_date)

    return total_scraped


def run_group_posts(urls, limit=10, min_comments=0, cookies=None, fb_dtsg=None,
                    download_images=True, should_stop=None,
                    start_date=None, end_date=None):
    """Scrape posts + comments from one or more groups."""
    _init_session(cookies, fb_dtsg)

    from .group_posts import fetch_posts
    from .comments import fetch_comments_for_post
    from .storage import save_post_data

    total_scraped = 0
    for i, url in enumerate(urls, 1):
        if should_stop and should_stop():
            log("Stop requested — halting")
            break

        log(f"\n[Group {i}/{len(urls)}] {url}")
        name_state = {"name": None}

        def process_batch(batch_posts, total_so_far, total_limit):
            nonlocal total_scraped
            for post in batch_posts:
                if should_stop and should_stop():
                    break
                post_id = post.get("post_id")
                if not post_id:
                    continue
                log(f"  Processing post {post_id}...")
                try:
                    comments, _ = fetch_comments_for_post(post_id, should_stop=should_stop)
                    save_post_data("group_post", post_id, post, comments)
                except Exception as e:
                    log(f"  Error fetching comments: {e} — saving post without comments")
                    save_post_data("group_post", post_id, post, [])
                total_scraped += 1
                import time
                time.sleep(1)

        fetch_posts(url, limit=limit, min_comments=min_comments,
                    download_images=download_images, batch_size=2,
                    on_batch_complete=process_batch, should_stop=should_stop,
                    group_name_state=name_state,
                    start_date=start_date, end_date=end_date)

    return total_scraped
