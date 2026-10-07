# Facebook Scraper 🕷️

A self-hosted Facebook scraping tool with a clean **Flask web GUI** — extract posts, comments, reactions, and images from Facebook pages, groups, and individual posts, without the official Facebook API.

Available as a **desktop app** (Windows `.exe` / macOS `.dmg`) or run from source.

## 📸 Screenshots

**Jobs** — every scrape tracked with status, sources and one-click logs/download:

![Jobs view](docs/screenshot-jobs.png)

**Posts** — browse, filter, and export what you've scraped:

![Posts view](docs/screenshot-posts.png)

Raw URLs (for tool integrations):

- `https://raw.githubusercontent.com/mohdtalal3/facebook_post_comment_scraper/main/docs/screenshot-jobs.png`
- `https://raw.githubusercontent.com/mohdtalal3/facebook_post_comment_scraper/main/docs/screenshot-posts.png`
- `https://raw.githubusercontent.com/mohdtalal3/facebook_post_comment_scraper/main/docs/screenshot-scrape.png`

## ✨ Features

**Scraping**
- ⚡ Three modes: **Single Post** · **Page Posts** · **Group Posts**
- 📅 **Start/end date filtering** — page feeds are filtered server-side, both modes stop paginating once posts fall below the start date
- 💬 Full comments with **nested replies**, author names, author IDs, profile URLs
- 👍 **Reaction counts**, share counts, and comment counts on every post
- 🖼️ **Image downloading** (toggle) with automatic album traversal for 5+ image posts
- 🔁 Robust retry logic with automatic proxy rotation on blocks/auth failures
- 🔐 Optional authenticated session (cookie string or pasted cURL) for private content your account can access

**Job management**
- 📋 Every scrape runs as a **named job** — name it yourself or let it auto-name
- 📜 **Live logs** streamed to the browser while a job runs; full transcripts saved per job
- 🗂️ Open a job to browse **only its posts** — type/source/search filters apply within the job
- ⏹️ Cooperative stop button

**Export & browsing**
- 📦 **ZIP export at every level**: single post, multi-select posts, whole job, or everything
- 🔗 Every post carries a permalink — one click to open it on Facebook
- 🔍 Filter by type, source (page/group name), text search, minimum comments
- 🗑️ Delete posts you don't need

**Proxies**
- 🌐 Rotating proxy (anonymous sessions) and static proxy (cookie sessions) — configurable right in the UI, persisted to `data/settings.json`

## 🚀 Quick start

### Desktop app (easiest)

Grab `FacebookScraper-x.x.x-windows.exe` or `FacebookScraper-x.x.x-macos.dmg` from the [latest release](../../releases) and run it — the UI opens in your browser automatically.

> **macOS first launch:** the app is ad-hoc signed (no paid Apple cert), so Gatekeeper asks for confirmation once.
> Right-click the app → **Open** → Open. If it says "damaged", run:
> `xattr -cr /Applications/FacebookScraper.app`
> The app picks the next free port automatically if 5001 is taken.

### Run from source

```bash
pip install -r requirements.txt
python run.py            # → http://127.0.0.1:5001
python run.py --port 8080 --debug
```

### Run with Docker

```bash
docker compose up -d
# or without compose:
docker build -t facebook-scraper .
docker run -p 5001:5001 -v ./data:/app/data facebook-scraper
```

Open http://localhost:5001. Scraped data and settings (proxies, etc.) persist in `./data` on the host — proxies saved in the UI survive rebuilds.

## 📖 Usage

1. **Scrape** — pick a mode, paste URLs (one per line), set post limit / min comments / date range, toggle images & comments, hit **Start scraping** and watch the live logs.
2. **Jobs** — every run shows up here with status and post count. **Open** a job to browse its posts (with filters scoped to it), **Logs** to see the full transcript, **Download** to get the whole job as a ZIP.
3. **Posts** (inside a job) — filter, view posts with nested comments, select multiple posts for ZIP export, or delete.
4. **Settings** — paste a cookie string or cURL command for authenticated scraping, and configure your proxies. All optional: public content works without any setup.

### Proxies (optional)

Configure in **Settings → Proxy** — saved to `data/settings.json` and reloaded automatically on startup (works in Docker too, since `data/` is the mounted volume).

## 📦 Output

Each post is saved under `data/`:

```
data/
├── jobs.json                                  # scrape job history
├── logs/{job_id}.txt                          # full log transcripts
├── simple_post/{post_id}/{post_id}.json
├── page_post/{page_name}/{post_id}/
│   ├── {post_id}.json                         # text, counts, media, comments
│   └── {post_id}.jpg ...                      # downloaded images
└── group_post/{group_name}/{post_id}/
```

Post JSON includes: `text`, `permalink`, `created_at`, `reaction_count`, `share_count`, `comment_count`, `media`, and `comments` with nested `replies` (each with author, author_id, author_url, reaction_count).

## 🏗️ Project structure

```
facebook/
├── run.py                  # Entry point
├── scraper/                # Scraping library (no web code)
│   ├── config.py           #   session state, paths, version
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
│   ├── storage.py          #   data/: save / list / filter / zip / delete
│   ├── auth.py             #   cookie / cURL parsing
│   └── tasks.py            #   high-level scrape jobs
└── web/                    # Flask app
    ├── jobs.py             #   background job manager + live logs
    ├── routes/             #   API: scrape, posts, jobs, settings
    ├── templates/          #   single-page UI
    └── static/             #   CSS + JS
```

## ⚠️ Disclaimer

This tool is for educational and personal archival purposes. Scraping Facebook may violate their Terms of Service — use responsibly, respect privacy, and don't scrape content you don't have permission to access.
