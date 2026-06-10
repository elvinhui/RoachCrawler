"""
fix_covers.py -- Batch replace all loremflickr cover images with unique picsum.photos URLs
seeded by filename hash so every article gets a different photo.
"""
import os
import re
import hashlib
import sys

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

POSTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'site_payload', 'content', 'posts')

def get_seed(filename):
    """用文件名生成唯一的数字 seed (200–1200 范围)"""
    h = int(hashlib.md5(filename.encode()).hexdigest(), 16)
    return (h % 1000) + 200

def fix_cover(filepath, filename):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    seed = get_seed(filename)
    new_url = f"https://picsum.photos/seed/{seed}/1200/600"

    # 替换所有 loremflickr URL
    new_content = re.sub(
        r'image:\s*"https://loremflickr\.com/[^"]*"',
        f'image: "{new_url}"',
        content
    )

    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[+] Updated: {filename}  -> seed={seed}  {new_url}")
    else:
        print(f"[~] Skipped: {filename}")

def main():
    files = [f for f in os.listdir(POSTS_DIR) if f.endswith('.md')]
    print(f"[*] Found {len(files)} posts, patching cover images...\n")
    for fname in sorted(files):
        fix_cover(os.path.join(POSTS_DIR, fname), fname)
    print(f"\n[+] Done!")

if __name__ == '__main__':
    main()
