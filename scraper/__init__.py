"""Facebook scraper package.

Modules:
    config      — shared session state (cookies, fb_dtsg, proxies)
    http        — retry logic + GraphQL response parsing
    resolvers   — URL -> user/group/post ID extraction
    extractors  — field extraction from Story nodes
    media       — image download + album traversal
    comments    — comment/reply scraping
    page_posts  — page/profile post scraping
    group_posts — group post scraping
    single_post — single post scraping (comments + images)
    storage     — data/ directory save/list/delete
    auth        — cookies / cURL / Chrome login helpers
"""
