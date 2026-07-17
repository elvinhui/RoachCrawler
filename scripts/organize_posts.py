"""
organize_posts.py — Hugo Post Migration Script
Organizes flat markdown files in content/posts/ into YYYY/MM/ subdirectories based on their frontmatter date.
Skips files that are already organized or don't have a valid date.
"""
import os
import re
import shutil

from datetime import datetime

POSTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'site_payload', 'content', 'posts'))

def parse_date(content):
    match = re.search(r'^date:\s*(.*?)\s*$', content, re.MULTILINE)
    if not match:
        return None
    date_str = match.group(1).strip().strip("'\"")
    try:
        # Try full ISO parsing
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        # Try simple YYYY-MM-DD
        try:
            return datetime.strptime(date_str[:10], '%Y-%m-%d')
        except ValueError:
            return None

def run_migration():
    print(f"[*] Starting post organization in: {POSTS_DIR}")
    
    # Only get files in the root of POSTS_DIR, ignore directories
    files = [f for f in os.listdir(POSTS_DIR) if os.path.isfile(os.path.join(POSTS_DIR, f)) and f.endswith('.md') and not f.startswith('_index')]
    
    if not files:
        print("[*] No unorganized files found in root directory.")
        return

    moved_count = 0
    failed_count = 0

    for filename in sorted(files):
        filepath = os.path.join(POSTS_DIR, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  [-] Error reading {filename}: {e}")
            failed_count += 1
            continue

        dt = parse_date(content)
        if not dt:
            print(f"  [-] Could not parse date for {filename}, skipping.")
            failed_count += 1
            continue

        # Target directory: YYYY/MM
        year_str = str(dt.year)
        month_str = f"{dt.month:02d}"
        target_dir = os.path.join(POSTS_DIR, year_str, month_str)
        
        os.makedirs(target_dir, exist_ok=True)
        
        target_filepath = os.path.join(target_dir, filename)
        
        shutil.move(filepath, target_filepath)
        moved_count += 1

    print(f"[*] Migration complete! Moved: {moved_count}, Failed/Skipped: {failed_count}")

if __name__ == '__main__':
    run_migration()
