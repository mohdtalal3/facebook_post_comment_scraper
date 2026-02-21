# Facebook Scraper 🕷️

A powerful Python-based Facebook scraping tool with a PyQt6 GUI interface for extracting posts, comments, and images from Facebook pages, groups, and individual posts without using the official Facebook API.

## 🎯 Key Highlights

- **Pure Requests-Based**: No browser automation or Selenium required - uses direct HTTP requests to Facebook's GraphQL API
- **Lightweight & Fast**: Minimal dependencies, efficient memory usage, and faster execution
- **No Browser Intervention**: Operates entirely through HTTP requests without spawning browser instances
- **Headless Operation**: Perfect for servers and automated workflows

## ✨ Features

- **Multiple Scraping Modes**:
  - 📄 Single post scraping (text, images, comments, and replies)
  - 👤 Page/Profile posts scraping
  - 👥 Facebook Group posts scraping
  - 🖼️ High-quality image extraction
  
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
  - Pure `requests` library implementation (no browser/Selenium)
  - Automatic retry mechanism with exponential backoff
  - Proxy support for privacy and rate limiting
  - Pagination handling for large data sets
  - JSON export for easy data processing
  - Direct GraphQL API communication

## 🆕 Latest Enhancements (v2.0)

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

- **🛡️ Robust Error Handling**:
  - Safe pagination with proper break conditions
  - No infinite loops on empty responses
  - Comprehensive error logging
  - Graceful degradation on failures

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Valid Facebook session tokens (extracted from browser - one-time setup)
- No browser automation tools required (Selenium, Playwright, etc.)
- Works with pure HTTP requests

### Installation

1. Clone the repository:
```bash
git clone https://github.com/mohdtalal3/facebook_post_comment_scraper
cd facebook_post_comment_scraper
```

2. Install required dependencies (minimal and lightweight):
```bash
pip install requests PyQt6 python-dotenv
```

Note: Only `requests` is needed for scraping - no browser automation libraries required!

3. Create a `.env` file in the project root:
```env
# Optional: Add your proxy if needed
PROXY=http://your-proxy:port

# Optional: Add any other configuration
```

### Required Dependencies

Create a `requirements.txt` file:
```txt
requests>=2.28.0
PyQt6>=6.4.0
python-dotenv>=0.20.0
```

Install with:
```bash
pip install -r requirements.txt
```

## 📖 Usage

### GUI Mode (Recommended)

Launch the graphical interface:
```bash
python facebook_ui.py
```

The GUI provides three main tabs:
1. **Simple Post**: Scrape a single post with all its comments and images
2. **Page Posts**: Extract multiple posts from a Facebook page or profile
3. **Group Posts**: Scrape posts from Facebook groups

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

Add your proxy to the `.env` file:
```env
PROXY=http://username:password@proxy-server:port
```

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
- **Private Content**: Cannot access content that requires authentication beyond what's provided.

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
- Update authentication headers

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
