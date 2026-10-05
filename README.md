# Facebook Scraper 🕷️

A Python-based Facebook scraping tool with a **Flask web GUI** for extracting posts, comments, and images from Facebook pages, groups, and individual posts — without the official Facebook API.

## Quick start

```bash
pip install -r requirements.txt
python run.py            # opens on http://127.0.0.1:5001
```

Then open the browser and use the three views:

- **Scrape** — pick a mode (Single Post / Page Posts / Group Posts), paste URLs, set post limit + min comments, toggle image downloading, and watch **live logs** while it runs.
- **Posts** — browse everything you've scraped. Filter by type, source (page/group name), text search, and minimum comments. View posts with nested comments/replies, download the JSON, download images as a ZIP, or delete.
- **Settings** — configure an authenticated session (cookie string, pasted cURL, or one-click Chrome login via SeleniumBase). Optional — public content works without it.

## Project structure

```
facebook/
├── run.py                  # Entry point: python run.py
├── requirements.txt
├── .env                    # PROXY / STATIC_PROXY / ROTATING_PROXY
├── scraper/                # Scraping library (no web code)
│   ├── config.py           #   shared session state (cookies, fb_dtsg, proxies)
│   ├── logging_utils.py    #   thread-aware log() with pluggable sink
│   ├── http.py             #   retry logic + GraphQL response parsing
│   ├── proxy_utils.py      #   proxy rotation / block detection
│   ├── resolvers.py        #   URL → user/group/post ID
│   ├── extractors.py       #   counts, names, reel/video detection
│   ├── media.py            #   image download + album traversal
│   ├── comments.py         #   comments + nested replies
│   ├── page_posts.py       #   page/profile post scraping
│   ├── group_posts.py      #   group post scraping
│   ├── single_post.py      #   single post scraping (comments + images)
│   ├── storage.py          #   data/ directory: save / list / filter / delete
│   ├── auth.py             #   cookie parsing, cURL parsing, Chrome login
│   └── tasks.py            #   high-level scrape jobs used by the web app
├── web/                    # Flask app
│   ├── jobs.py             #   background job manager + live log buffer
│   ├── routes/             #   API blueprints (scrape, posts, settings)
│   ├── templates/          #   index.html (single-page UI)
│   └── static/             #   CSS + JS
└── data/                   # Scraped output
    ├── simple_post/{post_id}/
    ├── page_post/{page_name}/{post_id}/
    └── group_post/{group_name}/{post_id}/
```

Each scraped post is saved as `data/{type}/.../{post_id}.json` containing the post text, reaction/share/comment counts, media (with downloaded images alongside), and full comments with nested replies — including author names, author IDs, profile URLs, and reaction counts.

## Notes

- **Proxies** are read from `.env` (`PROXY`, `STATIC_PROXY`, `ROTATING_PROXY`). Cookie sessions use the static proxy; anonymous sessions use the rotating one. Failed proxies rotate automatically on retry.
- **One job at a time** — the UI disables Start while a job runs and offers a cooperative Stop.
- The old PyQt6 GUI (`facebook_ui.py`) has been replaced by this web UI.
