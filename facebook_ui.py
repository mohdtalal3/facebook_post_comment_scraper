import sys
import os
import json
import time
import re
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
        """Scrape a single post"""
        post_id = self.params['post_id']
        
        self.log(f"Fetching comments for post {post_id}...")
        comments = fetch_comments_for_post(post_id)
        
        # Save data
        post_data = {
            "post_id": post_id,
            "type": "simple_post"
        }
        
        save_post_data("simple_post", post_id, post_data, comments)
        self.log(f"✅ Done! Saved to simple_post/{post_id}/")
        self.finished_signal.emit(True, f"Successfully scraped {len(comments)} comments")
    
    def scrape_page_posts(self):
        """Scrape posts from a page"""
        page_id = self.params['page_id']
        count = self.params['count']
        
        # Update the USER_ID in post_scraper
        post_scraper.USER_ID = page_id
        post_scraper.BASE_HEADERS["referer"] = f"https://www.facebook.com/profile.php?id={page_id}"
        
        self.log(f"Fetching {count} posts from page {page_id}...")
        posts = fetch_page_posts(count)
        
        self.log(f"✓ Found {len(posts)} posts. Now fetching comments...")
        self.progress_signal.emit(0, len(posts))
        
        # Fetch comments for each post
        for i, post in enumerate(posts, 1):
            post_id = post.get("post_id")
            if not post_id:
                self.log(f"[{i}/{len(posts)}] ⚠️ Skipping post with no ID")
                self.progress_signal.emit(i, len(posts))
                continue
            
            self.log(f"[{i}/{len(posts)}] Processing post {post_id}...")
            
            try:
                comments = fetch_comments_for_post(post_id)
                save_post_data("page_post", post_id, post, comments)
                self.log(f"  ✓ Saved {len(comments)} comments")
                time.sleep(1)  # Be nice to the server
            except Exception as e:
                self.log(f"  ❌ Error fetching comments: {e}")
                # Save post data even if comments fail
                save_post_data("page_post", post_id, post, [])
            
            self.progress_signal.emit(i, len(posts))
        
        self.finished_signal.emit(True, f"Successfully scraped {len(posts)} posts")
    
    def scrape_group_posts(self):
        """Scrape posts from a group"""
        group_id = self.params['group_id']
        count = self.params['count']
        
        # Update the GROUP_ID in group_post_scraper_v2
        group_post_scraper_v2.GROUP_ID = group_id
        group_post_scraper_v2.HEADERS["referer"] = f"https://www.facebook.com/groups/{group_id}/"
        
        self.log(f"Fetching {count} posts from group {group_id}...")
        posts = fetch_group_posts(count)
        
        self.log(f"✓ Found {len(posts)} posts. Now fetching comments...")
        self.progress_signal.emit(0, len(posts))
        
        # Fetch comments for each post
        for i, post in enumerate(posts, 1):
            post_id = post.get("post_id")
            if not post_id:
                self.log(f"[{i}/{len(posts)}] ⚠️ Skipping post with no ID")
                self.progress_signal.emit(i, len(posts))
                continue
            
            self.log(f"[{i}/{len(posts)}] Processing post {post_id}...")
            
            try:
                comments = fetch_comments_for_post(post_id)
                save_post_data("group_post", post_id, post, comments)
                self.log(f"  ✓ Saved {len(comments)} comments")
                time.sleep(1)  # Be nice to the server
            except Exception as e:
                self.log(f"  ❌ Error fetching comments: {e}")
                # Save post data even if comments fail
                save_post_data("group_post", post_id, post, [])
            
            self.progress_signal.emit(i, len(posts))
        
        self.finished_signal.emit(True, f"Successfully scraped {len(posts)} posts")


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
        input_group = QGroupBox("Post Input")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        
        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Post URL:"))
        self.simple_post_url = QLineEdit()
        self.simple_post_url.setPlaceholderText("https://www.facebook.com/...")
        url_layout.addWidget(self.simple_post_url)
        input_layout.addLayout(url_layout)
        
        # Extract ID button
        extract_btn = QPushButton("Extract Post ID from URL")
        extract_btn.clicked.connect(self.extract_simple_post_id)
        input_layout.addWidget(extract_btn)
        
        # OR separator
        input_layout.addWidget(QLabel("— OR —"))
        
        # Direct ID input
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Post ID:"))
        self.simple_post_id = QLineEdit()
        self.simple_post_id.setPlaceholderText("Enter post ID directly")
        id_layout.addWidget(self.simple_post_id)
        input_layout.addLayout(id_layout)
        
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
        input_group = QGroupBox("Page Input")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        
        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Page URL:"))
        self.page_url = QLineEdit()
        self.page_url.setPlaceholderText("https://www.facebook.com/...")
        url_layout.addWidget(self.page_url)
        input_layout.addLayout(url_layout)
        
        # Extract ID button
        extract_btn = QPushButton("Extract Page ID from URL")
        extract_btn.clicked.connect(self.extract_page_id)
        input_layout.addWidget(extract_btn)
        
        # OR separator
        input_layout.addWidget(QLabel("— OR —"))
        
        # Direct ID input
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Page ID:"))
        self.page_id = QLineEdit()
        self.page_id.setPlaceholderText("Enter page/user ID directly")
        id_layout.addWidget(self.page_id)
        input_layout.addLayout(id_layout)
        
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
        input_group = QGroupBox("Group Input")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        
        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Group URL:"))
        self.group_url = QLineEdit()
        self.group_url.setPlaceholderText("https://web.facebook.com/groups/668881464321714/")
        url_layout.addWidget(self.group_url)
        input_layout.addLayout(url_layout)
        
        # Extract ID button
        extract_btn = QPushButton("Extract Group ID from URL")
        extract_btn.clicked.connect(self.extract_group_id)
        input_layout.addWidget(extract_btn)
        
        # OR separator
        input_layout.addWidget(QLabel("— OR —"))
        
        # Direct ID input
        id_layout = QHBoxLayout()
        id_layout.addWidget(QLabel("Group ID:"))
        self.group_id = QLineEdit()
        self.group_id.setPlaceholderText("Enter group ID directly")
        id_layout.addWidget(self.group_id)
        input_layout.addLayout(id_layout)
        
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
    
    def extract_simple_post_id(self):
        """Extract post ID from URL"""
        url = self.simple_post_url.text().strip()
        if not url:
            self.show_error("Please enter a post URL")
            return
        
        self.log("Extracting post ID from URL...")
        post_id = extract_post_id_from_url(url)
        
        if post_id:
            self.simple_post_id.setText(post_id)
            self.log(f"✅ Extracted Post ID: {post_id}")
        else:
            self.show_error("Could not extract post ID from URL")
    
    def extract_page_id(self):
        """Extract page ID from URL"""
        url = self.page_url.text().strip()
        if not url:
            self.show_error("Please enter a page URL")
            return
        
        self.log("Extracting page ID from URL...")
        page_id = extract_user_id_from_url(url)
        
        if page_id:
            self.page_id.setText(page_id)
            self.log(f"✅ Extracted Page ID: {page_id}")
        else:
            self.show_error("Could not extract page ID from URL")
    
    def extract_group_id(self):
        """Extract group ID from URL"""
        url = self.group_url.text().strip()
        if not url:
            self.show_error("Please enter a group URL")
            return
        
        # Extract group ID from URL pattern
        # https://web.facebook.com/groups/668881464321714/
        match = re.search(r'/groups/(\d+)', url)
        
        if match:
            group_id = match.group(1)
            self.group_id.setText(group_id)
            self.log(f"✅ Extracted Group ID: {group_id}")
        else:
            self.show_error("Could not extract group ID from URL. Make sure URL contains /groups/[ID]")
    
    def scrape_simple_post(self):
        """Start scraping a simple post"""
        post_id = self.simple_post_id.text().strip()
        
        if not post_id:
            self.show_error("Please enter a post ID or extract from URL")
            return
        
        # Start scraping in background thread
        self.log("Starting simple post scraper...")
        params = {'post_id': post_id}
        self.start_scraping("simple_post", params)
    
    def scrape_page_posts(self):
        """Start scraping page posts"""
        page_id = self.page_id.text().strip()
        count = self.page_post_count.value()
        
        if not page_id:
            self.show_error("Please enter a page ID or extract from URL")
            return
        
        # Start scraping in background thread
        self.log(f"Starting page posts scraper (fetching {count} posts)...")
        params = {'page_id': page_id, 'count': count}
        self.start_scraping("page_posts", params)
    
    def scrape_group_posts(self):
        """Start scraping group posts"""
        group_id = self.group_id.text().strip()
        count = self.group_post_count.value()
        
        if not group_id:
            self.show_error("Please enter a group ID or extract from URL")
            return
        
        # Start scraping in background thread
        self.log(f"Starting group posts scraper (fetching {count} posts)...")
        params = {'group_id': group_id, 'count': count}
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
