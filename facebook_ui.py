import sys
import os
import json
import time
import re
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QComboBox, QSpinBox, QTabWidget,
                             QProgressBar, QGroupBox, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QTextCursor

# Import scraper modules
from main import (extract_user_id_from_url, extract_post_id_from_url, 
                 fetch_comments_for_post, save_post_data)
from post_scraper import fetch_posts as fetch_page_posts
from group_post_scraper_v2 import fetch_posts as fetch_group_posts
import post_scraper
import group_post_scraper_v2
import single_post_image


class ScraperThread(QThread):
    """Background thread for scraping operations"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, scraper_type, params):
        super().__init__()
        self.scraper_type = scraper_type
        self.params = params
    
    def log(self, message):
        """Emit log message"""
        self.log_signal.emit(message)
    
    def run(self):
        """Run the scraping task"""
        try:
            if self.scraper_type == "simple_post":
                self.scrape_simple_post()
            elif self.scraper_type == "page_posts":
                self.scrape_page_posts()
            elif self.scraper_type == "group_posts":
                self.scrape_group_posts()
            else:
                self.finished_signal.emit(False, "Invalid scraper type")
        except Exception as e:
            self.finished_signal.emit(False, f"Error: {str(e)}")
    
    def scrape_simple_post(self):
        """Scrape one or more posts"""
        urls = self.params['urls']  # List of URLs
        
        total = len(urls)
        self.progress_signal.emit(0, total)
        
        for i, url in enumerate(urls, 1):
            self.log(f"\n[{i}/{total}] Processing URL: {url}")
            
            # Extract post ID from URL
            self.log(f"  Extracting post ID...")
            post_id = extract_post_id_from_url(url)
            
            if not post_id:
                self.log(f"  ❌ Could not extract post ID from URL")
                self.progress_signal.emit(i, total)
                continue
            
            self.log(f"  ✅ Extracted Post ID: {post_id}")
            
            try:
                self.log(f"  Fetching comments...")
                comments, post_info = fetch_comments_for_post(post_id)
                
                # Save data
                post_data = {
                    "post_id": post_id,
                    "type": "simple_post",
                    "post_info": post_info
                }
                
                save_post_data("simple_post", post_id, post_data, comments)
                self.log(f"  💾 Saved to simple_post/{post_id}/{post_id}.json")
            except Exception as e:
                self.log(f"  ❌ Error processing post {post_id}: {e}")
                self.progress_signal.emit(i, total)
                continue
            
            # Fetch images if media_id is available
            if post_info and post_info.get("media_id"):
                media_id = post_info["media_id"]
                self.log(f"📸 Fetching images for media_id: {media_id}")
                
                image_folder = os.path.join("simple_post", post_id)
                
                try:
                    current_node = media_id
                    visited = set()
                    image_count = 0
                    
                    while current_node and current_node not in visited:
                        visited.add(current_node)
                        
                        payload = single_post_image.build_payload(current_node, post_id)
                        r = requests.post(single_post_image.GRAPHQL_URL, 
                                        headers=single_post_image.HEADERS, 
                                        data=payload, 
                                        proxies=single_post_image.PROXIES)
                        
                        cleaned_blocks = single_post_image.process_raw_graphql(r.text)
                        if not cleaned_blocks:
                            break
                        
                        # Extract image
                        image_url = None
                        for block in cleaned_blocks:
                            if "currMedia" in block:
                                image_url = block["currMedia"].get("image", {}).get("uri")
                                break
                        
                        if image_url:
                            image_count += 1
                            filename = single_post_image.download_image(image_url, image_folder, post_id, image_count)
                            if filename:
                                self.log(f"    ✓ Downloaded {filename}")
                        
                        # Get next node
                        next_node = None
                        for block in cleaned_blocks:
                            if "nextMediaAfterNodeId" in block and block["nextMediaAfterNodeId"]:
                                node_id_next = block["nextMediaAfterNodeId"].get("id")
                                if node_id_next:
                                    next_node = node_id_next
                                    break
                        
                        if next_node:
                            current_node = next_node
                        else:
                            if image_count > 0:
                                self.log(f"  ✅ Downloaded {image_count} images")
                            break
                            
                except Exception as e:
                    self.log(f"  ⚠️ Error fetching images: {e}")
            
            self.progress_signal.emit(i, total)
            time.sleep(1)  # Be nice to the server
        
        self.finished_signal.emit(True, f"Successfully scraped {total} post(s)")
    
    def scrape_page_posts(self):
        """Scrape posts from one or more pages"""
        urls = self.params['urls']  # List of URLs
        count = self.params['count']
        
        total_pages = len(urls)
        all_posts_count = 0
        
        for page_num, url in enumerate(urls, 1):
            self.log(f"\n[Page {page_num}/{total_pages}] Processing URL: {url}")
            
            # Extract page ID from URL
            self.log(f"  Extracting page ID...")
            page_id = extract_user_id_from_url(url)
            
            if not page_id:
                self.log(f"  ❌ Could not extract page ID from URL")
                continue
            
            self.log(f"  ✅ Extracted Page ID: {page_id}")
            
            try:
                # Update the USER_ID in post_scraper
                post_scraper.USER_ID = page_id
                post_scraper.BASE_HEADERS["referer"] = f"https://www.facebook.com/profile.php?id={page_id}"
                
                self.log(f"  Fetching {count} posts from page {page_id}...")
                posts = fetch_page_posts(count)
                
                self.log(f"  ✓ Found {len(posts)} posts. Now fetching comments...")
                
                # Fetch comments for each post
                for i, post in enumerate(posts, 1):
                    post_id = post.get("post_id")
                    if not post_id:
                        self.log(f"    [{i}/{len(posts)}] ⚠️ Skipping post with no ID")
                        continue
                    
                    self.log(f"    [{i}/{len(posts)}] Processing post {post_id}...")
                    
                    try:
                        comments, _ = fetch_comments_for_post(post_id)
                        save_post_data("page_post", post_id, post, comments)
                        self.log(f"      ✓ Saved to page_post/{post_id}/{post_id}.json")
                        time.sleep(1)  # Be nice to the server
                    except Exception as e:
                        self.log(f"      ❌ Error fetching comments: {e}")
                        # Save post data even if comments fail
                        save_post_data("page_post", post_id, post, [])
                
                all_posts_count += len(posts)
                
            except Exception as e:
                self.log(f"  ❌ Error processing page: {e}")
                continue
        
        self.finished_signal.emit(True, f"Successfully scraped {all_posts_count} posts from {total_pages} page(s)")
    
    def scrape_group_posts(self):
        """Scrape posts from one or more groups"""
        urls = self.params['urls']  # List of URLs
        count = self.params['count']
        
        total_groups = len(urls)
        all_posts_count = 0
        
        for group_num, url in enumerate(urls, 1):
            self.log(f"\n[Group {group_num}/{total_groups}] Processing URL: {url}")
            
            # Extract group ID from URL
            self.log(f"  Extracting group ID...")
            match = re.search(r'/groups/(\d+)', url)
            
            if not match:
                self.log(f"  ❌ Could not extract group ID from URL")
                continue
            
            group_id = match.group(1)
            self.log(f"  ✅ Extracted Group ID: {group_id}")
            
            try:
                # Update the GROUP_ID in group_post_scraper_v2
                group_post_scraper_v2.GROUP_ID = group_id
                group_post_scraper_v2.HEADERS["referer"] = f"https://www.facebook.com/groups/{group_id}/"
                
                self.log(f"  Fetching {count} posts from group {group_id}...")
                posts = fetch_group_posts(count)
                
                self.log(f"  ✓ Found {len(posts)} posts. Now fetching comments...")
                
                # Fetch comments for each post
                for i, post in enumerate(posts, 1):
                    post_id = post.get("post_id")
                    if not post_id:
                        self.log(f"    [{i}/{len(posts)}] ⚠️ Skipping post with no ID")
                        continue
                    
                    self.log(f"    [{i}/{len(posts)}] Processing post {post_id}...")
                    
                    try:
                        comments, _ = fetch_comments_for_post(post_id)
                        save_post_data("group_post", post_id, post, comments)
                        self.log(f"      ✓ Saved to group_post/{post_id}/{post_id}.json")
                        time.sleep(1)  # Be nice to the server
                    except Exception as e:
                        self.log(f"      ❌ Error fetching comments: {e}")
                        # Save post data even if comments fail
                        save_post_data("group_post", post_id, post, [])
                
                all_posts_count += len(posts)
                
            except Exception as e:
                self.log(f"  ❌ Error processing group: {e}")
                continue
        
        self.finished_signal.emit(True, f"Successfully scraped {all_posts_count} posts from {total_groups} group(s)")


class FacebookScraperUI(QMainWindow):
    """Main UI window for Facebook Scraper"""
    
    def __init__(self):
        super().__init__()
        self.scraper_thread = None
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Facebook Scraper")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Title
        title = QLabel("📘 Facebook Scraper")
        title.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Tab widget for different scraper types
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Create tabs
        self.simple_post_tab = self.create_simple_post_tab()
        self.page_posts_tab = self.create_page_posts_tab()
        self.group_posts_tab = self.create_group_posts_tab()
        
        self.tabs.addTab(self.simple_post_tab, "Simple Post")
        self.tabs.addTab(self.page_posts_tab, "Page Posts")
        self.tabs.addTab(self.group_posts_tab, "Group Posts")
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Log area
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(self.clear_log)
        log_layout.addWidget(clear_log_btn)
        
        main_layout.addWidget(log_group)
    
    def create_simple_post_tab(self):
        """Create the Simple Post tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Input group
        input_group = QGroupBox("Post Input (Multiple URLs Supported)")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        
        # URL input (textarea for multiple URLs)
        input_layout.addWidget(QLabel("Post URLs (one per line):"))
        self.simple_post_urls = QTextEdit()
        self.simple_post_urls.setPlaceholderText("https://www.facebook.com/share/p/...\nhttps://www.facebook.com/...\n(one URL per line)")
        self.simple_post_urls.setMaximumHeight(100)
        input_layout.addWidget(self.simple_post_urls)
        
        layout.addWidget(input_group)
        
        # Scrape button
        scrape_btn = QPushButton("🚀 Scrape Comments")
        scrape_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-size: 14px; padding: 10px; }")
        scrape_btn.clicked.connect(self.scrape_simple_post)
        layout.addWidget(scrape_btn)
        
        layout.addStretch()
        return tab
    
    def create_page_posts_tab(self):
        """Create the Page Posts tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Input group
        input_group = QGroupBox("Page Input (Multiple URLs Supported)")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        
        # URL input (textarea for multiple URLs)
        input_layout.addWidget(QLabel("Page URLs (one per line):"))
        self.page_urls = QTextEdit()
        self.page_urls.setPlaceholderText("https://www.facebook.com/profile.php?id=...\nhttps://www.facebook.com/...\n(one URL per line)")
        self.page_urls.setMaximumHeight(100)
        input_layout.addWidget(self.page_urls)
        
        # Post count
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Number of posts:"))
        self.page_post_count = QSpinBox()
        self.page_post_count.setMinimum(1)
        self.page_post_count.setMaximum(100)
        self.page_post_count.setValue(5)
        count_layout.addWidget(self.page_post_count)
        count_layout.addStretch()
        input_layout.addLayout(count_layout)
        
        layout.addWidget(input_group)
        
        # Scrape button
        scrape_btn = QPushButton("🚀 Scrape Page Posts")
        scrape_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-size: 14px; padding: 10px; }")
        scrape_btn.clicked.connect(self.scrape_page_posts)
        layout.addWidget(scrape_btn)
        
        layout.addStretch()
        return tab
    
    def create_group_posts_tab(self):
        """Create the Group Posts tab"""
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Input group
        input_group = QGroupBox("Group Input (Multiple URLs Supported)")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        
        # URL input (textarea for multiple URLs)
        input_layout.addWidget(QLabel("Group URLs (one per line):"))
        self.group_urls = QTextEdit()
        self.group_urls.setPlaceholderText("https://web.facebook.com/groups/668881464321714/\nhttps://www.facebook.com/groups/...\n(one URL per line)")
        self.group_urls.setMaximumHeight(100)
        input_layout.addWidget(self.group_urls)
        
        # Post count
        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Number of posts:"))
        self.group_post_count = QSpinBox()
        self.group_post_count.setMinimum(1)
        self.group_post_count.setMaximum(100)
        self.group_post_count.setValue(5)
        count_layout.addWidget(self.group_post_count)
        count_layout.addStretch()
        input_layout.addLayout(count_layout)
        
        layout.addWidget(input_group)
        
        # Scrape button
        scrape_btn = QPushButton("🚀 Scrape Group Posts")
        scrape_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-size: 14px; padding: 10px; }")
        scrape_btn.clicked.connect(self.scrape_group_posts)
        layout.addWidget(scrape_btn)
        
        layout.addStretch()
        return tab
    
    def scrape_simple_post(self):
        """Start scraping simple posts from URLs"""
        urls_text = self.simple_post_urls.toPlainText().strip()
        
        if not urls_text:
            self.show_error("Please enter post URLs")
            return
        
        # Parse URLs
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        if not urls:
            self.show_error("No valid URLs found")
            return
        
        # Start scraping in background thread
        self.log(f"Starting simple post scraper for {len(urls)} URL(s)...")
        params = {'urls': urls}
        self.start_scraping("simple_post", params)
    
    def scrape_page_posts(self):
        """Start scraping posts from page URLs"""
        urls_text = self.page_urls.toPlainText().strip()
        count = self.page_post_count.value()
        
        if not urls_text:
            self.show_error("Please enter page URLs")
            return
        
        # Parse URLs
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        if not urls:
            self.show_error("No valid URLs found")
            return
        
        # Start scraping in background thread
        self.log(f"Starting page posts scraper for {len(urls)} page(s) (fetching {count} posts each)...")
        params = {'urls': urls, 'count': count}
        self.start_scraping("page_posts", params)
    
    def scrape_group_posts(self):
        """Start scraping posts from group URLs"""
        urls_text = self.group_urls.toPlainText().strip()
        count = self.group_post_count.value()
        
        if not urls_text:
            self.show_error("Please enter group URLs")
            return
        
        # Parse URLs
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        if not urls:
            self.show_error("No valid URLs found")
            return
        
        # Start scraping in background thread
        self.log(f"Starting group posts scraper for {len(urls)} group(s) (fetching {count} posts each)...")
        params = {'urls': urls, 'count': count}
        self.start_scraping("group_posts", params)
    
    def start_scraping(self, scraper_type, params):
        """Start the scraping thread"""
        if self.scraper_thread and self.scraper_thread.isRunning():
            self.show_error("A scraping task is already running. Please wait.")
            return
        
        # Create and start thread
        self.scraper_thread = ScraperThread(scraper_type, params)
        self.scraper_thread.log_signal.connect(self.log)
        self.scraper_thread.progress_signal.connect(self.update_progress)
        self.scraper_thread.finished_signal.connect(self.scraping_finished)
        
        # Disable UI
        self.tabs.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.scraper_thread.start()
    
    def scraping_finished(self, success, message):
        """Handle scraping completion"""
        # Re-enable UI
        self.tabs.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.log(f"✅ {message}")
            QMessageBox.information(self, "Success", message)
        else:
            self.log(f"❌ {message}")
            self.show_error(message)
    
    def update_progress(self, current, total):
        """Update progress bar"""
        if total > 0:
            progress = int((current / total) * 100)
            self.progress_bar.setValue(progress)
    
    def log(self, message):
        """Add message to log"""
        self.log_text.append(message)
        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def clear_log(self):
        """Clear the log"""
        self.log_text.clear()
    
    def show_error(self, message):
        """Show error message"""
        QMessageBox.critical(self, "Error", message)
        self.log(f"❌ {message}")


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern style
    
    window = FacebookScraperUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
