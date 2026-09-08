# Facebook Scraper 🕷️

A powerful Python-based Facebook scraping tool with a PyQt6 GUI interface for extracting posts, comments, and images from Facebook pages, groups, and individual posts without using the official Facebook API. It supports public scraping without cookies and authenticated scraping with cookies/`fb_dtsg` for content your Facebook account can access.

## 🎯 Key Highlights

- **Pure Requests-Based Scraping**: Scraping uses direct HTTP requests to Facebook's GraphQL API without browser automation
- **Lightweight & Fast**: Minimal dependencies, efficient memory usage, and faster execution
- **No Browser Intervention**: Operates entirely through HTTP requests without spawning browser instances
- **Headless Operation**: Perfect for servers and automated workflows

## ✨ Features

- **Multiple Scraping Modes**:
  - 📄 Single post scraping from one or many post URLs
  - 💬 Comments and nested replies from posts
  - 👤 Page/Profile posts scraping with comments and images
  - 👥 Facebook Group posts scraping with comments and images
  - 🖼️ High-quality image extraction and album traversal
  - 🔐 Cookie-based access for private posts, pages, and groups your account can view
  
- **Rich Data Extraction**:
  - Post content (text, reactions, shares)
  - Comments and nested replies
  - User information (names, IDs, profile links)
  - Media content (images with multiple resolution support)
  - Timestamps and engagement metrics

- **User-Friendly GUI**:
  - PyQt6-based desktop interface
  - Real-time logging and progress tracking
  - Tabbed interface for different scraping types
  - Easy configuration and export

- **Robust Architecture**:
  - Pure `requests` scraping flow for Facebook GraphQL endpoints
  - Optional SeleniumBase helper for capturing browser cookies and `fb_dtsg`
  - Automatic retry mechanism with exponential backoff
  - Rotating and static proxy support for public and cookie-based sessions
  - Pagination handling for large data sets
  - JSON export for easy data processing
  - Direct GraphQL API communication

## 🆕 Latest Enhancements (v2.0)

- **🔐 Authenticated Private Content Support**:
  - Paste Facebook cookies and `fb_dtsg` directly in the GUI
  - Uses your logged-in session for private posts, pages, and groups you are allowed to view
  - Switches to static proxy mode when cookies are configured

- **🌐 Improved Proxy Handling**:
  - Supports `ROTATING_PROXY` for public scraping
  - Supports `STATIC_PROXY` for cookie-based scraping
  - Rotates static proxy ports when proxy errors or IP blocks are detected

- **🎯 Enhanced Comment Detection**:
  - 6 extraction paths for comment counts
  - Handles deeply nested comment structures
  - Ensures posts with 49+ comments are correctly detected
  - Never skips posts due to missing comment count data

- **🔍 Advanced Story Node Discovery**:
  - Multi-location Story node detection (Group edges, timeline edges, direct nodes)
  - Handles complex JSON structures from Facebook's varying response formats
  - Discovers posts that were previously hidden in nested structures

- **📸 Complete Album Scraping**:
  - Automatically fetches ALL images from posts (up to 50 per post)
  - Uses media ID iteration to navigate through large albums
  - No longer limited to first 5 images
  - Perfect for posts with 10-20+ images

- **♻️ Smart Deduplication**:
  - Detects already-scraped posts by checking saved JSON files
  - Skips duplicate posts when resuming interrupted sessions
  - Saves bandwidth and processing time
  - Automatic folder structure validation

- **🔄 Intelligent Retry Logic**:
  - 3-attempt retry for transient Facebook API errors
  - 2-second delays between retry attempts
  - Handles empty response arrays gracefully
  - Prevents infinite loops on persistent failures

- **🎬 Content Filtering**:
  - Automatic reel and video post detection and skipping
  - Configurable minimum comment threshold
  - Focus on high-engagement photo posts only
  - Video download is not currently supported

- **🛡️ Robust Error Handling**:
  - Safe pagination with proper break conditions
  - No infinite loops on empty responses
  - Comprehensive error logging
  - Graceful degradation on failures

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- No browser automation tools required (Selenium, Playwright, etc.)
- Works with pure HTTP requests

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mohdtalal3/facebook_post_comment_scraper
cd facebook_post_comment_scraper
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

Note: The scraping flow uses `requests`; `seleniumbase` is included as an optional helper for capturing cookies and `fb_dtsg` from a browser session.

3. Create a `.env` file in the project root:
```env

# Optional rotating proxy for public/no-cookie scraping
ROTATING_PROXY=http://username:password@rotating-proxy-server:port

# Optional static proxy for cookie/private scraping
STATIC_PROXY=http://username:password@static-proxy-server:port
```


## 📖 Usage

### GUI Mode (Recommended)

Launch the graphical interface:
```bash
python facebook_ui.py
```

The GUI provides three main tabs:
1. **Simple Post**: Scrape one or multiple post URLs with comments, replies, and images
2. **Page Posts**: Extract multiple posts from a Facebook page/profile with comments and images
3. **Group Posts**: Scrape posts from Facebook groups with comments and images

Use **Configure Cookies & FB_DTSG** when scraping private content or content that requires login. The scraper can only access private posts, pages, or groups that your Facebook account already has permission to view.

### CLI Mode

For advanced users, you can use the command-line interface:

```python
from main import extract_post_id_from_url, fetch_comments_for_post, save_post_data

# Extract post ID
post_id = extract_post_id_from_url("https://www.facebook.com/permalink.php?story_fbid=123...")

# Fetch comments
comments = fetch_comments_for_post(post_id, max_comments=100)

# Save data
save_post_data(post_id, comments, "output_dir")
```

## 🔧 Configuration

### Proxy Configuration

Add proxy values to the `.env` file:
```env
PROXY=http://username:password@proxy-server:port
ROTATING_PROXY=http://username:password@rotating-proxy-server:port
STATIC_PROXY=http://username:password@static-proxy-server:port
```

- `ROTATING_PROXY` is used when scraping without cookies.
- `STATIC_PROXY` is used when cookies are configured, which helps keep the logged-in session on a stable IP.
- `PROXY` is used as a fallback if the more specific proxy value is missing.

### Cookies and `fb_dtsg`

For private posts, private pages, private groups, or login-only content:

1. Log in to Facebook in your browser.
2. Open the GUI with `python facebook_ui.py`.
3. Click **Configure Cookies & FB_DTSG**.
4. Paste your Facebook cookie string.
5. Paste the current `fb_dtsg` token if available.
6. Start scraping the post, page, or group URL.

Private scraping only works for content your account can normally view in Facebook.

## 🎥 Tutorial Videos

Add your published tutorial URLs below:

| Topic | Video Link |
| --- | --- |
| How to setup `facebook_post_comment_scraper` | `[Add video link here]` |
| How to fetch comments/images from a single post | `[Add video link here]` |
| How to fetch comments, images, and posts from a group | `[Add video link here]` |
| How to fetch from a page | `[Add video link here]` |
| How to fetch if post, page, or group is private | `[Add video link here]` |

## 📁 Project Structure

```
facebook-scraper/
├── main.py                      # Main orchestration and utilities
├── facebook_ui.py               # PyQt6 GUI interface
├── post_scraper.py              # Page/Profile post scraper
├── group_post_scraper_v2.py     # Group post scraper
├── comment_scraper.py           # Comment and reply scraper
├── single_post_image.py         # Image extraction module
├── simple_post/                 # Output directory for posts
├── page_post/                   # Output directory for page posts
├── ex/                          # Example outputs
└── extras/                      # Additional scripts and tools
```

## 📊 Output Format

Data is saved in JSON format with the following structure:

### Post Data
```json
{
  "post_id": "123456789",
  "author": "User Name",
  "author_id": "100001234567890",
  "content": "Post text content",
  "timestamp": "2024-01-01T12:00:00",
  "reactions": 150,
  "shares": 25,
  "images": ["url1.jpg", "url2.jpg"],
  "comments_count": 45
}
```

### Comment Data
```json
{
  "comment_id": "987654321",
  "author": "Commenter Name",
  "author_id": "100009876543210",
  "text": "Comment text",
  "timestamp": "2024-01-01T12:30:00",
  "replies": [...]
}
```

## ⚠️ Important Notes

### Legal & Ethical Considerations

- **Terms of Service**: This tool may violate Facebook's Terms of Service. Use at your own risk.
- **Rate Limiting**: Implement appropriate delays between requests to avoid detection.
- **Privacy**: Respect user privacy and data protection laws (GDPR, CCPA, etc.).
- **Personal Use**: This tool is intended for educational and research purposes only.

### Technical Limitations

- **Doc IDs**: Facebook's GraphQL document IDs change frequently. You'll need to update them periodically.
- **Authentication**: Requires valid Facebook session tokens that expire.
- **Rate Limits**: Excessive requests may result in temporary blocks or account restrictions.
- **Private Content**: Requires valid cookies and only works for private content your Facebook account can access.

## 🛠️ Troubleshooting

### Common Issues

**1. "Failed after 5 attempts" error**
- Check your internet connection
- Verify proxy settings
- Update DOC_ID values
- Ensure session tokens are valid

**2. No data returned**
- Verify the URL/ID is correct
- Check if content is publicly accessible
- For private content, configure cookies and `fb_dtsg`
- Update authentication headers or GraphQL document IDs if Facebook changed them

**3. GUI not launching**
- Ensure PyQt6 is properly installed: `pip install --upgrade PyQt6`
- Check Python version compatibility

### Debug Mode

Enable verbose logging by modifying the scripts:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is provided for educational purposes only. Users are responsible for ensuring compliance with Facebook's Terms of Service and applicable laws.

## 🙏 Acknowledgments

- Built with Python and PyQt6
- Uses pure `requests` library for HTTP communication
- Direct GraphQL API integration (unofficial)
- No browser automation required
- Inspired by the need for lightweight, efficient data research tools

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting section

## ⚡ Roadmap

**Completed:**
- [x] Enhanced comment count detection with 6 extraction paths
- [x] Advanced Story node discovery in nested structures
- [x] Complete album scraping (up to 50 images per post)
- [x] Post deduplication for interrupted sessions
- [x] Automatic retry logic for transient API errors
- [x] Robust pagination with proper error handling
- [x] Reel/video filtering
- [x] Configurable comment threshold filtering
- [x] Cookie and `fb_dtsg` support in the GUI
- [x] Static/rotating proxy selection

**Upcoming:**
- [ ] Add support for Facebook Stories
- [ ] Implement video download functionality
- [ ] Add data export to CSV/Excel
- [ ] Improve authentication flow
- [ ] Add scheduling and automation features
- [ ] Create web-based interface
- [ ] Add data analysis and visualization tools

---

**Disclaimer**: This tool is not affiliated with or endorsed by Facebook/Meta. Use responsibly and ethically.
