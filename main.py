import base64
import json
import os
import time
import requests
import re
from html import unescape

# Import scraper modules
from comment_scraper import fetch_comments, fetch_replies, session, fb_json, GRAPHQL
from post_scraper import fetch_posts as fetch_page_posts, extract_media as extract_page_media, parse_fb_response as parse_page_response
from group_post_scraper_v2 import fetch_posts as fetch_group_posts


def extract_user_id_from_url(url):
    """Extract Facebook User ID from a profile URL"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        print(f"  Fetching page: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        html = response.text
        
        # Try multiple patterns to find user ID
        patterns = [
            r'fb://profile/(\d+)',           # BEST signal
            r'"profile_owner":"(\d+)"',
            r'"userID":"(\d+)"',
            r'owner_id=(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                user_id = match.group(1)
                print(f"  ✅ Found User ID: {user_id}")
                return user_id
        
        print("  ❌ User ID not found (profile may be private or login wall)")
        return None
    
    except Exception as e:
        print(f"  ❌ Error fetching URL: {e}")
        return None


def extract_post_id_from_url(url):
    """Extract Facebook Post ID from a post URL"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        print(f"  Fetching post: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        html = response.text
        
        # Extract og:url meta tag
        og_url_match = re.search(
            r'<meta property="og:url" content="([^"]+)"',
            html
        )
        
        post_id = None
        
        if og_url_match:
            og_url = unescape(og_url_match.group(1))
            
            # Case 1: /posts/.../POST_ID/
            m = re.search(r'/posts/.+?/(\d+)/', og_url)
            
            # Case 2: permalink.php?story_fbid=POST_ID
            if not m:
                m = re.search(r'story_fbid=(\d+)', og_url)
            
            if m:
                post_id = m.group(1)
        
        if post_id:
            print(f"  ✅ Found Post ID: {post_id}")
            return post_id
        
        print("  ❌ Post ID not found in URL")
        return None
    
    except Exception as e:
        print(f"  ❌ Error fetching URL: {e}")
        return None


def convert_post_id_to_feedback_id(post_id):
    """Convert post_id to feedback_id using base64 encoding"""
    feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
    return feedback_id


def fetch_comments_for_post(post_id):
    """Fetch all comments and replies for a given post_id"""
    feedback_id = convert_post_id_to_feedback_id(post_id)
    print(f"  Fetching comments for post {post_id}...")
    print(f"  Using feedback_id: {feedback_id}")
    
    all_data = []
    comments = fetch_comments(feedback_id)
    
    for c in comments:
        print(f"    🗨️ {c['author']}: {c['text'][:50]}...")
        c["replies"] = fetch_replies(c)
        
        for r in c["replies"]:
            print(f"       ↳ {r['author']}: {r['text'][:50]}...")
        
        all_data.append(c)
    
    print(f"  ✓ Found {len(all_data)} comments")
    return all_data


def save_post_data(post_type, post_id, post_data, comments_data):
    """Save post and comments data in organized folder structure"""
    # Create folder structure: [post_type]/[post_id]/
    folder_path = os.path.join(post_type, post_id)
    os.makedirs(folder_path, exist_ok=True)
    
    # Save post data
    post_file = os.path.join(folder_path, "post.json")
    with open(post_file, "w", encoding="utf-8") as f:
        json.dump(post_data, f, ensure_ascii=False, indent=2)
    print(f"  📄 Saved post data to {post_file}")
    
    # Save comments data
    comments_file = os.path.join(folder_path, "comments.json")
    with open(comments_file, "w", encoding="utf-8") as f:
        json.dump(comments_data, f, ensure_ascii=False, indent=2)
    print(f"  💬 Saved {len(comments_data)} comments to {comments_file}")


def display_menu():
    """Display the main menu"""
    print("\n" + "="*60)
    print("   📘 FACEBOOK SCRAPER")
    print("="*60)
    print("\nChoose what to scrape:")
    print("  1. Simple Post (just comments from a single post)")
    print("  2. Page Posts (posts + comments from a page)")
    print("  3. Group Posts (posts + comments from a group)")
    print("  4. Exit")
    print("="*60)


def scrape_simple_post():
    """Scrape comments from a single post"""
    print("\n--- SIMPLE POST SCRAPER ---")
    print("\nChoose input method:")
    print("  1. Enter Post URL (auto-extract ID)")
    print("  2. Enter Post ID directly")
    
    input_choice = input("Your choice (1 or 2): ").strip()
    
    post_id = None
    
    if input_choice == "1":
        post_url = input("Enter Post URL: ").strip()
        if not post_url:
            print("❌ Invalid URL")
            return
        
        # Extract post ID from URL
        post_id = extract_post_id_from_url(post_url)
        if not post_id:
            print("❌ Could not extract Post ID from URL")
            return
    
    elif input_choice == "2":
        post_id = input("Enter Post ID: ").strip()
        if not post_id:
            print("❌ Invalid post ID")
            return
    
    else:
        print("❌ Invalid choice")
        return
    
    print(f"\nFetching comments for post {post_id}...")
    comments = fetch_comments_for_post(post_id)
    
    # Save data
    post_data = {
        "post_id": post_id,
        "type": "simple_post"
    }
    
    save_post_data("simple_post", post_id, post_data, comments)
    print(f"\n✅ Done! Saved to simple_post/{post_id}/")


def scrape_page_posts():
    """Scrape posts and comments from a page"""
    print("\n--- PAGE POST SCRAPER ---")
    print("\nChoose input method:")
    print("  1. Enter Page URL (auto-extract ID)")
    print("  2. Enter Page/User ID directly")
    
    input_choice = input("Your choice (1 or 2): ").strip()
    
    page_id = None
    
    if input_choice == "1":
        page_url = input("Enter Page URL: ").strip()
        if not page_url:
            print("❌ Invalid URL")
            return
        
        # Extract user ID from URL
        page_id = extract_user_id_from_url(page_url)
        if not page_id:
            print("❌ Could not extract User ID from URL")
            return
    
    elif input_choice == "2":
        page_id = input("Enter Page/User ID: ").strip()
        if not page_id:
            print("❌ Invalid page ID")
            return
    
    else:
        print("❌ Invalid choice")
        return
    
    try:
        count = int(input("How many posts to fetch? ").strip())
    except ValueError:
        print("❌ Invalid number")
        return
    
    # Update the USER_ID in post_scraper
    import post_scraper
    post_scraper.USER_ID = page_id
    post_scraper.HEADERS["referer"] = f"https://www.facebook.com/profile.php?id={page_id}"
    
    print(f"\nFetching {count} posts from page {page_id}...")
    posts = fetch_page_posts(count)
    
    print(f"\n✓ Found {len(posts)} posts. Now fetching comments...")
    
    # Fetch comments for each post
    for i, post in enumerate(posts, 1):
        post_id = post.get("post_id")
        if not post_id:
            print(f"\n[{i}/{len(posts)}] ⚠️ Skipping post with no ID")
            continue
        
        print(f"\n[{i}/{len(posts)}] Processing post {post_id}...")
        
        try:
            comments = fetch_comments_for_post(post_id)
            save_post_data("page_post", post_id, post, comments)
            time.sleep(1)  # Be nice to the server
        except Exception as e:
            print(f"  ❌ Error fetching comments: {e}")
            # Save post data even if comments fail
            save_post_data("page_post", post_id, post, [])
    
    print(f"\n✅ Done! Saved {len(posts)} posts to page_post/")


def scrape_group_posts():
    """Scrape posts and comments from a group"""
    print("\n--- GROUP POST SCRAPER ---")
    group_id = input("Enter Group ID: ").strip()
    
    if not group_id:
        print("❌ Invalid group ID")
        return
    
    try:
        count = int(input("How many posts to fetch? ").strip())
    except ValueError:
        print("❌ Invalid number")
        return
    
    # Update the GROUP_ID in group_post_scraper_v2
    import group_post_scraper_v2
    group_post_scraper_v2.GROUP_ID = group_id
    group_post_scraper_v2.HEADERS["referer"] = f"https://www.facebook.com/groups/{group_id}/"
    
    print(f"\nFetching {count} posts from group {group_id}...")
    posts = fetch_group_posts(count)
    
    print(f"\n✓ Found {len(posts)} posts. Now fetching comments...")
    
    # Fetch comments for each post
    for i, post in enumerate(posts, 1):
        post_id = post.get("post_id")
        if not post_id:
            print(f"\n[{i}/{len(posts)}] ⚠️ Skipping post with no ID")
            continue
        
        print(f"\n[{i}/{len(posts)}] Processing post {post_id}...")
        
        try:
            comments = fetch_comments_for_post(post_id)
            save_post_data("group_post", post_id, post, comments)
            time.sleep(1)  # Be nice to the server
        except Exception as e:
            print(f"  ❌ Error fetching comments: {e}")
            # Save post data even if comments fail
            save_post_data("group_post", post_id, post, [])
    
    print(f"\n✅ Done! Saved {len(posts)} posts to group_post/")


def main():
    """Main function - GUI-like menu"""
    while True:
        display_menu()
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            scrape_simple_post()
        elif choice == "2":
            scrape_page_posts()
        elif choice == "3":
            scrape_group_posts()
        elif choice == "4":
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid choice. Please enter 1, 2, 3, or 4.")
        
        # Ask if user wants to continue
        if choice in ["1", "2", "3"]:
            continue_choice = input("\nPress Enter to return to menu (or 'q' to quit): ").strip().lower()
            if continue_choice == 'q':
                print("\n👋 Goodbye!")
                break


if __name__ == "__main__":
    main()
